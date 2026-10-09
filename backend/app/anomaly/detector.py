"""Rule-based anomaly detection over match results (initial classification, before agent refinement)."""
from __future__ import annotations

import logging
from typing import Dict, List, Sequence, Tuple

from app.anomaly import rules
from app.core.config import Settings
from app.domain import (ACCOUNTING, AMOUNT_MISMATCH, BANK, DUPLICATE_TRANSACTION, HIGH_VALUE_MISMATCH,
                        MISSING_TRANSACTION, POTENTIALLY_SUSPICIOUS, SUSPICIOUS_DISCLAIMER, TIMING_DIFFERENCE, UNMATCHED,
                        Anomaly, DuplicateGroup, MatchResult, Txn, new_id)
from app.utils.amounts import format_money

log = logging.getLogger(__name__)


def high_value_description(diff: float, s: Settings, cur: str = "INR") -> str:
    return (f"Mismatch of {format_money(diff, cur)} meets or exceeds the high-value threshold of "
            f"{format_money(s.high_value_threshold, cur)}.")


def detect_anomalies(bank: Sequence[Txn], accounting: Sequence[Txn], matches: Sequence[MatchResult],
                     s: Settings) -> Tuple[List[Anomaly], List[DuplicateGroup]]:
    bank_by = {t.id: t for t in bank}
    acct_by = {t.id: t for t in accounting}
    matched_bank = {m.bank_id for m in matches if m.accounting_id and m.status != UNMATCHED}
    matched_acct = {m.accounting_id for m in matches if m.accounting_id and m.status != UNMATCHED}
    anomalies: List[Anomaly] = []

    # 1. duplicates (per source). Only reported when at least one member lacks a confident counterpart.
    groups: List[DuplicateGroup] = []
    explained: set = set()
    for source, txns, matched in ((BANK, bank, matched_bank), (ACCOUNTING, accounting, matched_acct)):
        for g in rules.find_duplicate_groups(txns, s):
            unresolved = [i for i in g.txn_ids if i not in matched]
            if not unresolved:
                continue
            original = next((i for i in g.txn_ids if i in matched), g.txn_ids[0])
            dups = [i for i in g.txn_ids if i != original and i not in matched] or [i for i in g.txn_ids if i != original]
            groups.append(g)
            for d in dups:
                explained.add(d)
                t = (bank_by if source == BANK else acct_by)[d]
                anomalies.append(Anomaly(
                    id=new_id(), transaction_id=d, related_transaction_id=original, anomaly_type=DUPLICATE_TRANSACTION,
                    severity=rules.severity_for(DUPLICATE_TRANSACTION, t.amount, s), source=source,
                    confidence=g.confidence, description=g.explanation,
                    details={"duplicate_group_id": g.id, "transaction_ids": g.txn_ids, "original_transaction_id": original,
                             "confidence": g.confidence}))

    # 2. matched pairs with differences
    for m in matches:
        if not m.accounting_id or m.status == UNMATCHED:
            continue
        b, a = bank_by[m.bank_id], acct_by[m.accounting_id]
        diff = m.amount_difference or 0.0
        if diff > s.amount_epsilon:
            anomalies.append(Anomaly(
                id=new_id(), transaction_id=b.id, related_transaction_id=a.id, anomaly_type=AMOUNT_MISMATCH,
                severity=rules.severity_for(AMOUNT_MISMATCH, diff, s), source=BANK, confidence=round(m.score / 100, 2),
                description=(f"Bank amount {format_money(b.amount, b.currency)} differs from accounting amount "
                             f"{format_money(a.amount, a.currency)} by {format_money(diff, b.currency)}."),
                details={"amount_difference": diff, "bank_amount": b.amount, "accounting_amount": a.amount,
                         "date_diff_days": m.date_diff_days, "match_score": m.score}))
            if rules.is_high_value(diff, s):
                anomalies.append(Anomaly(
                    id=new_id(), transaction_id=b.id, related_transaction_id=a.id, anomaly_type=HIGH_VALUE_MISMATCH,
                    severity="HIGH", source=BANK, confidence=round(m.score / 100, 2),
                    description=high_value_description(diff, s, b.currency),
                    details={"amount_difference": diff, "threshold": s.high_value_threshold}))
        elif (m.date_diff_days or 0) > s.strict_date_tolerance_days:
            anomalies.append(Anomaly(
                id=new_id(), transaction_id=b.id, related_transaction_id=a.id, anomaly_type=TIMING_DIFFERENCE,
                severity="LOW", source=BANK, confidence=round(m.score / 100, 2),
                description=(f"Same amount ({format_money(b.amount, b.currency)}) recorded {m.date_diff_days} day(s) "
                             f"apart in bank and accounting records."),
                details={"date_diff_days": m.date_diff_days, "match_score": m.score}))

    # 3. unmatched records -> MISSING_TRANSACTION (+ high value, + conservative suspicious flag)
    known_vendors = sorted({t.vendor_key for t in accounting if t.vendor_key})
    for t in bank:
        if t.id in matched_bank or t.id in explained:
            continue
        anomalies.append(Anomaly(
            id=new_id(), transaction_id=t.id, anomaly_type=MISSING_TRANSACTION, source=BANK, confidence=0.7,
            severity=rules.severity_for(MISSING_TRANSACTION, t.amount, s),
            description=f"Bank transaction of {format_money(t.amount, t.currency)} on {t.date.isoformat()} has no "
                        f"matching accounting entry.",
            details={"side": BANK}))
        if rules.is_high_value(t.amount, s):
            anomalies.append(Anomaly(
                id=new_id(), transaction_id=t.id, anomaly_type=HIGH_VALUE_MISMATCH, severity="HIGH", source=BANK,
                confidence=0.7, description=high_value_description(t.amount, s, t.currency),
                details={"amount_difference": t.amount, "threshold": s.high_value_threshold, "unmatched": True}))
        ind = rules.suspicious_indicators(t, s, known_vendors)
        if len(ind) >= s.suspicious_min_indicators:
            anomalies.append(Anomaly(
                id=new_id(), transaction_id=t.id, anomaly_type=POTENTIALLY_SUSPICIOUS, severity="HIGH", source=BANK,
                confidence=0.5, description=f"{SUSPICIOUS_DISCLAIMER} Indicators: "
                                            + "; ".join(rules.INDICATOR_TEXT[i] for i in ind) + ".",
                details={"indicators": ind}))
    for t in accounting:
        if t.id in matched_acct or t.id in explained:
            continue
        anomalies.append(Anomaly(
            id=new_id(), transaction_id=t.id, anomaly_type=MISSING_TRANSACTION, source=ACCOUNTING, confidence=0.7,
            severity="HIGH" if rules.is_high_value(t.amount, s) else "MEDIUM",
            description=f"Accounting entry of {format_money(t.amount, t.currency)} on {t.date.isoformat()} has no "
                        f"matching bank transaction (possibly unpresented/delayed or recorded in error).",
            details={"side": ACCOUNTING}))
    log.info("Anomaly detection: %d anomalies, %d duplicate groups", len(anomalies), len(groups))
    return anomalies, groups
