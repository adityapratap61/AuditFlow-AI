"""Candidate-filtered, one-to-one transaction matching (levels 1-4; level 5 = agent relaxed retry)."""
from __future__ import annotations

import logging
from bisect import bisect_left, bisect_right
from collections import defaultdict
from typing import Dict, Iterable, List, Tuple

from app.core.config import Settings
from app.domain import UNMATCHED, MatchResult, Txn
from app.matching.fuzzy_matcher import description_similarity
from app.matching.scoring import MatchScore, ScoreWeights, classify_score, score_pair
from app.matching.tolerance import relaxed_tolerance, strict_tolerance

log = logging.getLogger(__name__)


class TransactionIndex:
    """Indexes for fast candidate lookup: by amount (cents), by reference key, by date range."""

    def __init__(self, txns: Iterable[Txn]):
        self.txns: List[Txn] = list(txns)
        self.by_id: Dict[str, Txn] = {t.id: t for t in self.txns}
        self._cents: Dict[int, List[Txn]] = defaultdict(list)
        self._refs: Dict[str, List[Txn]] = defaultdict(list)
        for t in self.txns:
            self._cents[round(t.amount * 100)].append(t)
            for k in t.ref_keys:
                self._refs[k].append(t)
        self._sorted = sorted(self.txns, key=lambda t: t.date)
        self._ords = [t.date.toordinal() for t in self._sorted]

    def by_amount(self, amount: float, eps: float = 0.01) -> List[Txn]:
        c = round(amount * 100)
        out: List[Txn] = []
        for key in (c - 1, c, c + 1):
            out.extend(t for t in self._cents.get(key, ()) if abs(t.amount - amount) <= eps)
        return out

    def by_reference(self, keys: Iterable[str]) -> List[Txn]:
        seen: Dict[str, Txn] = {}
        for k in keys:
            for t in self._refs.get(k, ()):
                seen[t.id] = t
        return list(seen.values())

    def in_date_range(self, center, days: int) -> List[Txn]:
        o = center.toordinal()
        return self._sorted[bisect_left(self._ords, o - days):bisect_right(self._ords, o + days)]


def _level(score: MatchScore, s: Settings) -> int:
    if score.reference_match:
        return 1
    if score.amount_difference <= s.amount_epsilon:
        return 2 if score.description_similarity < s.description_candidate_threshold else 3
    return 4


class Matcher:
    def __init__(self, settings: Settings):
        self.s = settings
        self.weights = ScoreWeights.from_settings(settings)
        self.strict = strict_tolerance(settings)
        self.relaxed = relaxed_tolerance(settings)

    def candidates(self, b: Txn, idx: TransactionIndex) -> Dict[str, Txn]:
        s = self.s
        cands: Dict[str, Txn] = {}
        for t in idx.by_reference(b.ref_keys):  # level 1: reference (any date)
            cands[t.id] = t
        window = idx.in_date_range(b.date, self.strict.date_days)  # strict date window for levels 2-4
        for t in idx.by_amount(b.amount, s.amount_epsilon):  # levels 2/3: exact amount + close date
            if self.strict.date_ok(b.date, t.date):
                cands[t.id] = t
        for t in window:  # level 4: close amount + fuzzy description + close date
            if t.id in cands or not self.relaxed.amount_ok(b.amount, t.amount):
                continue
            if description_similarity(b, t) >= s.description_candidate_threshold:
                cands[t.id] = t
        return cands

    def match(self, bank: List[Txn], accounting: List[Txn]) -> List[MatchResult]:
        idx = TransactionIndex(accounting)
        pairs: List[Tuple[float, int, int, int, MatchScore, Txn, Txn]] = []
        for bi, b in enumerate(bank):
            for t in self.candidates(b, idx).values():
                sc = score_pair(b, t, self.s, self.weights, self.strict, self.relaxed)
                if sc.total >= self.s.review_threshold:
                    pairs.append((sc.total, -sc.date_diff_days, -bi, _level(sc, self.s), sc, b, t))
        pairs.sort(key=lambda p: (p[0], p[1], p[2]), reverse=True)
        used_b, used_a = set(), set()
        results: Dict[str, MatchResult] = {}
        for total, _, _, level, sc, b, t in pairs:
            if b.id in used_b or t.id in used_a:
                continue
            used_b.add(b.id)
            used_a.add(t.id)
            results[b.id] = to_match_result(b, t, sc, self.s, level)
        out = [results.get(b.id) or MatchResult(bank_id=b.id, accounting_id=None, score=0.0, status=UNMATCHED,
                                                reasons=["no accounting candidate reached the review threshold"])
               for b in bank]
        log.info("Matching done: bank=%d accounting=%d matched_pairs=%d", len(bank), len(accounting), len(results))
        return out


def to_match_result(b: Txn, t: Txn, sc: MatchScore, s: Settings, level: int, matched_by: str = "ENGINE") -> MatchResult:
    return MatchResult(
        bank_id=b.id, accounting_id=t.id, score=sc.total, status=classify_score(sc.total, s), level=level,
        signals={**{f"{k}_score": v for k, v in sc.signals.items()}}, reasons=sc.reasons,
        date_diff_days=sc.date_diff_days, description_similarity=sc.description_similarity,
        amount_difference=sc.amount_difference, matched_by=matched_by)
