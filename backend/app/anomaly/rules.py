"""Deterministic, conservative anomaly rules. Nothing here ever asserts fraud."""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, List, Optional, Sequence, Tuple

from app.core.config import Settings
from app.domain import (AMOUNT_MISMATCH, DUPLICATE_TRANSACTION, HIGH_VALUE_MISMATCH, MISSING_TRANSACTION,
                        POTENTIALLY_SUSPICIOUS, TIMING_DIFFERENCE, DuplicateGroup, Txn, new_id)
from app.matching.fuzzy_matcher import description_similarity, text_similarity
from app.utils.amounts import format_money

_GENERIC = re.compile(r"\b(cash|unknown|misc\w*|suspense|adjustment|self|bearer|others?)\b")
INDICATOR_TEXT = {
    "ROUND_HIGH_VALUE": "round high-value amount",
    "NEAR_THRESHOLD": "amount just below the high-value threshold",
    "GENERIC_DESCRIPTION": "generic or non-specific description",
    "UNKNOWN_VENDOR": "counterparty not found anywhere in the accounting records",
}


def is_high_value(amount: float, s: Settings) -> bool:
    return amount >= s.high_value_threshold


def severity_for(anomaly_type: str, amount: float, s: Settings) -> str:
    if anomaly_type in (HIGH_VALUE_MISMATCH, POTENTIALLY_SUSPICIOUS):
        return "HIGH"
    if anomaly_type == TIMING_DIFFERENCE:
        return "LOW"
    if anomaly_type in (MISSING_TRANSACTION, AMOUNT_MISMATCH, DUPLICATE_TRANSACTION):
        return "HIGH" if is_high_value(amount, s) else "MEDIUM"
    return "MEDIUM"


# ------------------------------------------------------------------ duplicates
def duplicate_pair_confidence(a: Txn, b: Txn, s: Settings) -> Optional[Tuple[float, List[str]]]:
    if a.transaction_type != b.transaction_type or abs(a.amount - b.amount) > s.amount_epsilon:
        return None
    dd = abs((a.date - b.date).days)
    ref_eq = bool(a.normalized_reference and a.normalized_reference == b.normalized_reference)
    sim = description_similarity(a, b)
    reasons = ["identical amount"]
    if ref_eq and dd <= 7:
        reasons.append("identical reference")
        return min(0.99, 0.9 + (0.05 if sim >= 75 else 0.0)), reasons
    if dd <= 1 and sim >= 75:
        conf = 0.4 + 0.4 * sim / 100.0 - (0.1 if dd == 1 else 0.0)
        reasons.append("same date" if dd == 0 else "dates one day apart")
        reasons.append(f"description similarity {sim:.0f}%")
        return round(min(conf, 0.99), 2), reasons
    return None


def find_duplicate_groups(txns: Sequence[Txn], s: Settings) -> List[DuplicateGroup]:
    buckets: Dict[int, List[Txn]] = defaultdict(list)
    for t in txns:
        buckets[round(t.amount * 100)].append(t)
    parent: Dict[str, str] = {}

    def find(x: str) -> str:
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    edge_conf: Dict[Tuple[str, str], Tuple[float, List[str]]] = {}
    for items in buckets.values():
        if len(items) < 2:
            continue
        items = items[:60]  # bound pairwise work for pathological buckets
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                res = duplicate_pair_confidence(items[i], items[j], s)
                if res and res[0] >= s.duplicate_min_confidence:
                    edge_conf[(items[i].id, items[j].id)] = res
                    parent[find(items[i].id)] = find(items[j].id)
    groups: Dict[str, List[str]] = defaultdict(list)
    by_id = {t.id: t for t in txns}
    for tid in list(parent):
        groups[find(tid)].append(tid)
    out: List[DuplicateGroup] = []
    for ids in groups.values():
        if len(ids) < 2:
            continue
        ids.sort(key=lambda i: (by_id[i].date, by_id[i].row_number or 0))
        confs = [c for (a, b), (c, _) in edge_conf.items() if a in ids and b in ids]
        conf = round(min(confs), 2) if confs else 0.7
        first = by_id[ids[0]]
        out.append(DuplicateGroup(
            id=new_id(), source=first.source, txn_ids=ids, confidence=conf,
            explanation=(f"{len(ids)} {first.source.lower()} records share the amount "
                         f"{format_money(first.amount, first.currency)} with the same/similar date and description; "
                         f"they likely represent the same transaction recorded more than once.")))
    return out


# ------------------------------------------------------------------ suspicious (very conservative)
def suspicious_indicators(txn: Txn, s: Settings, known_vendor_keys: Sequence[str]) -> List[str]:
    out: List[str] = []
    thr = s.high_value_threshold
    if txn.amount >= thr and round(txn.amount) % 1000 == 0:
        out.append("ROUND_HIGH_VALUE")
    if 0.9 * thr <= txn.amount < thr:
        out.append("NEAR_THRESHOLD")
    if _GENERIC.search(txn.normalized_description):
        out.append("GENERIC_DESCRIPTION")
    if known_vendor_keys:
        key = txn.vendor_key or txn.normalized_description
        best = max((text_similarity(key, k) for k in known_vendor_keys), default=0.0)
        if not key or best < 60:
            out.append("UNKNOWN_VENDOR")
    return out
