"""Multi-signal match scoring (amount, date, description, reference) with configurable weights."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from app.core.config import Settings
from app.domain import LIKELY_MATCH, MATCHED, REVIEW_REQUIRED, UNMATCHED, Txn
from app.matching.fuzzy_matcher import description_similarity, has_description_info
from app.matching.tolerance import Tolerance, amount_diff, date_diff_days, relaxed_tolerance, strict_tolerance
from app.utils.amounts import format_money


@dataclass
class ScoreWeights:
    amount: float = 40.0
    date: float = 20.0
    description: float = 20.0
    reference: float = 20.0

    @classmethod
    def from_settings(cls, s: Settings) -> "ScoreWeights":
        return cls(s.amount_score_weight, s.date_score_weight, s.description_score_weight, s.reference_score_weight)


@dataclass
class MatchScore:
    total: float
    signals: Dict[str, float]  # points earned per signal
    applicable: Dict[str, bool]
    date_diff_days: int
    amount_difference: float
    description_similarity: float
    reference_match: bool
    reasons: List[str] = field(default_factory=list)


def reference_signal(a: Txn, b: Txn):
    """Return (applicable, fraction, reason)."""
    if a.normalized_reference and b.normalized_reference:
        if a.normalized_reference == b.normalized_reference:
            return True, 1.0, "reference numbers are identical"
        if a.ref_keys & b.ref_keys:
            return True, 1.0, "a reference token appears on both records"
        return True, 0.0, "reference numbers differ"
    shared = a.ref_keys & b.ref_keys
    if shared:
        return True, 1.0, "a reference/invoice token appears on both records"
    return False, 0.0, "no comparable reference"


def score_pair(bank: Txn, acct: Txn, s: Settings, weights: ScoreWeights | None = None,
               strict: Tolerance | None = None, relaxed: Tolerance | None = None) -> MatchScore:
    w = weights or ScoreWeights.from_settings(s)
    strict = strict or strict_tolerance(s)
    relaxed = relaxed or relaxed_tolerance(s)
    reasons: List[str] = []
    cur = bank.currency or "INR"

    # amount
    adiff = amount_diff(bank, acct)
    if adiff <= s.amount_epsilon:
        a_frac, reasons = 1.0, reasons + ["amount is identical"]
    elif strict.amount_pct > 0 and strict.amount_ok(bank.amount, acct.amount):
        a_frac, reasons = 0.9, reasons + [f"amount within strict tolerance (difference {format_money(adiff, cur)})"]
    elif relaxed.amount_ok(bank.amount, acct.amount):
        a_frac = s.amount_partial_credit
        reasons.append(f"amount differs by {format_money(adiff, cur)} (within relaxed tolerance)")
    else:
        a_frac = 0.0
        reasons.append(f"amount differs by {format_money(adiff, cur)} (outside tolerance)")

    # date
    dd = date_diff_days(bank, acct)
    if dd <= strict.date_days:
        d_frac = 1.0
        reasons.append("same date" if dd == 0 else f"date differs by {dd} day(s) (within strict tolerance)")
    elif dd <= relaxed.date_days:
        d_frac = 0.5
        reasons.append(f"date differs by {dd} day(s) (within relaxed tolerance)")
    else:
        d_frac = 0.0
        reasons.append(f"date differs by {dd} day(s) (outside tolerance)")

    # description
    sim = description_similarity(bank, acct)
    desc_applicable = has_description_info(bank, acct)
    reasons.append(f"description similarity {sim:.0f}%")

    # reference
    r_app, r_frac, r_reason = reference_signal(bank, acct)
    reasons.append(r_reason)

    signals = {
        "amount": round(w.amount * a_frac, 2),
        "date": round(w.date * d_frac, 2),
        "description": round(w.description * sim / 100.0, 2) if desc_applicable else 0.0,
        "reference": round(w.reference * r_frac, 2) if r_app else 0.0,
    }
    applicable = {"amount": True, "date": True, "description": desc_applicable, "reference": r_app}
    denom = sum(getattr(w, k) for k, v in applicable.items() if v)
    total = (sum(signals.values()) / denom * 100.0) if denom else 0.0
    # dissimilar descriptions can never be better than REVIEW unless a reference ties the pair together
    if desc_applicable and sim < s.description_min_for_likely and not (r_app and r_frac >= 1.0):
        cap = s.likely_match_threshold - 0.01
        if total > cap:
            total = cap
            reasons.append("score capped: descriptions are dissimilar")
    return MatchScore(total=round(total, 2), signals=signals, applicable=applicable, date_diff_days=dd,
                      amount_difference=adiff, description_similarity=sim, reference_match=r_app and r_frac >= 1.0,
                      reasons=reasons)


def classify_score(total: float, s: Settings) -> str:
    if total >= s.match_threshold:
        return MATCHED
    if total >= s.likely_match_threshold:
        return LIKELY_MATCH
    if total >= s.review_threshold:
        return REVIEW_REQUIRED
    return UNMATCHED
