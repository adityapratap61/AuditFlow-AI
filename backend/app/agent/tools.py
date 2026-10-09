"""Investigation tools. Each tool is deterministic, returns a ToolResult and is logged as an investigation step."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set

from app.anomaly.rules import duplicate_pair_confidence
from app.core.config import Settings
from app.domain import Txn
from app.matching.fuzzy_matcher import description_similarity, fuzzy_rank
from app.matching.matcher import TransactionIndex
from app.matching.scoring import MatchScore, ScoreWeights, score_pair
from app.matching.tolerance import Tolerance, relaxed_tolerance, strict_tolerance
from app.utils.amounts import format_money


@dataclass
class ToolResult:
    tool: str
    arguments: Dict[str, Any]
    candidates: List[Txn]
    summary: str
    data: Dict[str, Any] = field(default_factory=dict)

    @property
    def ids(self) -> List[str]:
        return [c.id for c in self.candidates]


class InvestigationToolbox:
    """Tools operating on the opposite-source pool (counterpart search) and same-source pool (duplicates).

    `taken` = ids of opposite-pool records already matched to a *different* transaction; they are excluded
    from counterpart candidates (but counted in the result summary).
    """

    def __init__(self, settings: Settings, opposite: TransactionIndex, same: TransactionIndex, taken: Set[str]):
        self.s = settings
        self.opposite = opposite
        self.same = same
        self.taken = taken
        self.strict: Tolerance = strict_tolerance(settings)
        self.relaxed: Tolerance = relaxed_tolerance(settings)
        self.weights = ScoreWeights.from_settings(settings)

    # ------------------------------------------------------------------ helpers
    def _split(self, items: Sequence[Txn]):
        avail = [t for t in items if t.id not in self.taken]
        return avail, len(items) - len(avail)

    def _result(self, tool: str, args: dict, items: Sequence[Txn], what: str, **data) -> ToolResult:
        avail, taken = self._split(items)
        extra = f" ({taken} already matched to other records)" if taken else ""
        return ToolResult(tool, args, avail, f"{len(avail)} available candidate(s) {what}{extra}", data)

    # ------------------------------------------------------------------ tools
    def search_by_amount(self, txn: Txn) -> ToolResult:
        items = self.opposite.by_amount(txn.amount, self.s.amount_epsilon)
        return self._result("search_by_amount", {"amount": txn.amount}, items, "with identical amount")

    def search_by_reference(self, txn: Txn) -> ToolResult:
        items = self.opposite.by_reference(txn.ref_keys)
        return self._result("search_by_reference", {"reference": txn.reference, "keys": len(txn.ref_keys)}, items,
                            "sharing a reference")

    def search_by_date_range(self, txn: Txn, days: int, candidates: Optional[Sequence[Txn]] = None) -> ToolResult:
        pool = candidates if candidates is not None else self.opposite.in_date_range(txn.date, days)
        items = [c for c in pool if abs((c.date - txn.date).days) <= days]
        res = self._result("search_by_date_range", {"date": txn.date.isoformat(), "days": days}, items,
                           f"within ±{days} day(s)")
        return res

    def search_by_description(self, txn: Txn, min_score: Optional[float] = None) -> ToolResult:
        min_score = self.s.description_candidate_threshold + 10 if min_score is None else min_score
        pool = self.opposite.in_date_range(txn.date, self.s.description_search_window_days)
        ranked = fuzzy_rank(txn, [c for c in pool if c.id not in self.taken], min_score)
        return ToolResult("search_by_description", {"min_score": min_score, "window_days": self.s.description_search_window_days},
                          [c for c, _ in ranked[:10]],
                          f"{len(ranked)} available candidate(s) with similar description (>= {min_score:.0f}%)",
                          {"similarity": {c.id: sc for c, sc in ranked[:10]}})

    def fuzzy_search_transactions(self, txn: Txn, candidates: Sequence[Txn]) -> ToolResult:
        ranked = fuzzy_rank(txn, candidates, 0.0)
        return ToolResult("fuzzy_search_transactions", {"candidates": len(candidates)}, [c for c, _ in ranked],
                          f"ranked {len(ranked)} candidate(s) by description similarity"
                          + (f"; best {ranked[0][1]:.0f}%" if ranked else ""),
                          {"similarity": {c.id: sc for c, sc in ranked}})

    def compare_transactions(self, a: Txn, b: Txn) -> ToolResult:
        sc: MatchScore = score_pair(a if a.source == "BANK" else b, b if a.source == "BANK" else a, self.s,
                                    self.weights, self.strict, self.relaxed)
        cmp = comparison_dict(a, b, sc)
        return ToolResult("compare_transactions", {}, [b], (
            f"amount difference {format_money(sc.amount_difference, a.currency)}, date difference "
            f"{sc.date_diff_days} day(s), description similarity {sc.description_similarity:.0f}%, "
            f"reference {'match' if sc.reference_match else 'no match'}, relaxed score {sc.total:.1f}"), {"comparison": cmp, "score": sc})

    def check_duplicates(self, txn: Txn) -> ToolResult:
        twins = []
        for t in self.same.by_amount(txn.amount, self.s.amount_epsilon):
            if t.id == txn.id:
                continue
            res = duplicate_pair_confidence(txn, t, self.s)
            if res and res[0] >= self.s.duplicate_min_confidence:
                twins.append((t, res[0], res[1]))
        twins.sort(key=lambda x: -x[1])
        return ToolResult("check_duplicates", {}, [t for t, _, _ in twins],
                          f"{len(twins)} probable duplicate record(s) in the same source",
                          {"confidence": {t.id: c for t, c, _ in twins}, "reasons": {t.id: r for t, _, r in twins}})

    def retry_with_relaxed_tolerance(self, txn: Txn) -> ToolResult:
        """Level 5: relaxed date (±N days) and relaxed amount tolerance, scored with the standard weights."""
        pool = self.opposite.in_date_range(txn.date, self.relaxed.date_days)
        scored = []
        for c in pool:
            if c.id in self.taken or not self.relaxed.amount_ok(txn.amount, c.amount):
                continue
            bank, acct = (txn, c) if txn.source == "BANK" else (c, txn)
            sc = score_pair(bank, acct, self.s, self.weights, self.strict, self.relaxed)
            if sc.total >= self.s.review_threshold:
                scored.append((c, sc))
        scored.sort(key=lambda x: -x[1].total)
        return ToolResult("retry_with_relaxed_tolerance",
                          {"date_days": self.relaxed.date_days, "amount_pct": self.relaxed.amount_pct},
                          [c for c, _ in scored],
                          f"{len(scored)} candidate(s) scoring >= {self.s.review_threshold:.0f} under relaxed tolerance "
                          f"(±{self.relaxed.date_days} days, ±{self.relaxed.amount_pct:g}% amount)",
                          {"scores": {c.id: sc.total for c, sc in scored}})


def comparison_dict(a: Txn, b: Txn, sc: MatchScore) -> Dict[str, Any]:
    return {
        "amount_a": a.amount, "amount_b": b.amount, "amount_difference": sc.amount_difference,
        "amount_equal": sc.amount_difference <= 0.01, "date_a": a.date.isoformat(), "date_b": b.date.isoformat(),
        "date_difference_days": sc.date_diff_days, "description_similarity": sc.description_similarity,
        "reference_match": sc.reference_match, "score": sc.total,
    }
