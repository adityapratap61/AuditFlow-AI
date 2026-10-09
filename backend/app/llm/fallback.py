"""Deterministic (no-LLM) explanations built only from structured evidence."""
from __future__ import annotations

from typing import Any, Dict, List

from app.domain import (AMOUNT_MISMATCH, DUPLICATE_TRANSACTION, MISSING_TRANSACTION, SUSPICIOUS_DISCLAIMER,
                        TIMING_DIFFERENCE)
from app.utils.amounts import format_money

ACTIONS = {
    TIMING_DIFFERENCE: "Confirm the posting date with the bank and accounting records; no correction is likely needed if the dates are explained.",
    AMOUNT_MISMATCH: "Review the source documents (invoice/payment advice) to determine which amount is correct and post an adjustment if required.",
    DUPLICATE_TRANSACTION: "Verify whether both records are genuine payments; reverse or void the duplicate if it is not.",
    MISSING_TRANSACTION: "Locate the supporting document and record the transaction (or confirm why it is absent).",
}


def _m(v, cur="INR"):
    return format_money(v, cur)


def fallback_explanation(ev: Dict[str, Any], flags: List[str] | None = None) -> Dict[str, Any]:
    t = ev["transaction"]
    cur = "INR"
    src = t["source"].lower()
    other = "accounting" if src == "bank" else "bank"
    kind = ev["conclusion"]
    cp = ev.get("counterpart")
    cmp = ev.get("comparison") or {}
    points: List[str] = [f"{src.capitalize()} transaction: {_m(t['amount'], cur)} on {t['date']} - {t['description']}"]
    if kind == TIMING_DIFFERENCE and cp:
        d = cmp.get("date_difference_days")
        text = (f"The {src} transaction of {_m(t['amount'], cur)} dated {t['date']} has no {other} match within the strict date "
                f"tolerance. A {other} record with the same amount and similar description was found dated {cp['date']}, "
                f"{d} day(s) apart. This is classified as a probable timing difference.")
        points += [f"{other.capitalize()} counterpart: {_m(cp['amount'], cur)} on {cp['date']}",
                   f"Date difference: {d} day(s)", f"Description similarity: {cmp.get('description_similarity', 0):.0f}%"]
        inference = "Probable timing difference (same transaction recorded on different dates)."
    elif kind == AMOUNT_MISMATCH and cp:
        text = (f"The {src} transaction of {_m(t['amount'], cur)} dated {t['date']} has a likely {other} counterpart dated "
                f"{cp['date']} with amount {_m(cp['amount'], cur)}, a difference of {_m(cmp.get('amount_difference', 0), cur)}. "
                f"This is classified as an amount mismatch.")
        points += [f"{other.capitalize()} counterpart: {_m(cp['amount'], cur)} on {cp['date']}",
                   f"Amount difference: {_m(cmp.get('amount_difference', 0), cur)}",
                   f"Reference match: {'yes' if cmp.get('reference_match') else 'no'}"]
        inference = "Probable amount mismatch for the same underlying transaction."
    elif kind == DUPLICATE_TRANSACTION:
        n = len(ev.get("duplicates") or [])
        conf = ev.get("duplicate_confidence")
        text = (f"The {src} transaction of {_m(t['amount'], cur)} dated {t['date']} appears to duplicate "
                f"{n or 'another'} record(s) with the same amount and a similar date and description in the same source"
                + (f" (confidence {conf:.0%})" if conf else "") + ". It is classified as a probable duplicate.")
        points += [f"Duplicate records found: {n}"]
        inference = "Probable duplicate entry."
    else:
        text = (f"The {src} transaction of {_m(t['amount'], cur)} dated {t['date']} has no {other} counterpart, even after "
                f"searching by amount, reference, description and relaxed date/amount tolerances. It is classified as a missing transaction.")
        if ev.get("rejected_candidates"):
            points.append("Candidates considered and rejected: " + "; ".join(ev["rejected_candidates"]))
        inference = f"Probable missing {other} entry."
    flags = flags or []
    if "HIGH_VALUE_MISMATCH" in flags:
        thr = ev["tolerances"]["high_value_threshold"]
        text += f" The amount at issue meets or exceeds the high-value threshold of {_m(thr, cur)}."
    if "POTENTIALLY_SUSPICIOUS" in flags:
        text += " " + SUSPICIOUS_DISCLAIMER
    text += " Manual verification is recommended."
    return {"explanation": text, "evidence_points": points, "inference": inference,
            "recommended_action": ACTIONS.get(kind, ACTIONS[MISSING_TRANSACTION]), "source": "fallback"}


def fallback_summary(summary: Dict[str, Any]) -> str:
    return (f"AuditFlow AI reconciled {summary['total_bank_transactions']} bank and {summary['total_accounting_transactions']} "
            f"accounting transactions: {summary['matched']} matched, {summary['likely_matches']} likely matches, "
            f"{summary['review_required']} requiring review and {summary['unmatched']} unmatched bank transactions. "
            f"{summary['total_anomalies']} anomalies were detected, of which {summary['high_risk']} are high risk. "
            f"Manual verification is recommended for all flagged items.")
