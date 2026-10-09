"""JSON / CSV reports for a completed reconciliation run."""
from __future__ import annotations

import csv
import datetime as dt
import io
from typing import Any, Dict

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.database import models as m
from app.domain import HIGH_VALUE_MISMATCH, POTENTIALLY_SUSPICIOUS, SUSPICIOUS_DISCLAIMER
from app.services.anomaly_service import SEVERITY_RANK, count_by_type
from app.services.reconciliation_service import get_run


def _txn_brief(t: m.Transaction | None) -> Dict[str, Any] | None:
    if t is None:
        return None
    return {"id": t.id, "source": t.source, "date": t.date.isoformat(), "amount": t.amount,
            "transaction_type": t.transaction_type, "description": t.raw_description, "reference": t.reference}


def _completed_run(db: Session, run_id: str) -> m.ReconciliationRun:
    run = get_run(db, run_id)
    if run.status != "completed":
        raise AppError(409, "RUN_NOT_COMPLETED", f"Reconciliation run is '{run.status}'; a report needs a completed run.")
    return run


def build_report(db: Session, run_id: str) -> Dict[str, Any]:
    s = get_settings()
    run = _completed_run(db, run_id)
    summary = dict(run.summary or {})
    narrative, nsrc = summary.pop("narrative", None), summary.pop("narrative_source", None)
    status = summary.pop("overall_status", None)
    dup_groups = summary.pop("duplicate_group_details", [])
    anomalies = sorted(db.scalars(select(m.Anomaly).where(m.Anomaly.run_id == run_id)).all(),
                       key=lambda a: (SEVERITY_RANK.get(a.severity, 3), a.anomaly_type))
    sev = {k: 0 for k in ("HIGH", "MEDIUM", "LOW")}
    for a in anomalies:
        sev[a.severity] = sev.get(a.severity, 0) + 1

    def row(a: m.Anomaly) -> Dict[str, Any]:
        return {"anomaly_id": a.id, "type": a.anomaly_type, "severity": a.severity, "description": a.description,
                "confidence": a.confidence, "transaction": _txn_brief(a.transaction),
                "related_transaction": _txn_brief(a.related_transaction), "explanation": a.explanation}

    invs = db.scalars(select(m.Investigation).where(m.Investigation.run_id == run_id)).all()
    report = {
        "report_metadata": {"product": s.app_name, "tagline": s.tagline, "version": s.version, "format": "json",
                            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "run_id": run.id,
                            "bank_file": run.bank_filename, "accounting_file": run.accounting_filename,
                            "processing_time_seconds": run.processing_time},
        "overall_status": status,
        "totals": {"bank_transactions": summary.get("total_bank_transactions"),
                   "accounting_transactions": summary.get("total_accounting_transactions"),
                   "matched": summary.get("matched"), "likely_matches": summary.get("likely_matches"),
                   "review_required": summary.get("review_required"), "unmatched": summary.get("unmatched"),
                   "unmatched_accounting": summary.get("unmatched_accounting"), "match_rate": summary.get("match_rate")},
        "summary": summary, "narrative": narrative, "narrative_source": nsrc,
        "anomaly_counts": count_by_type(a.anomaly_type for a in anomalies), "severity_counts": sev,
        "high_value_mismatches": [row(a) for a in anomalies if a.anomaly_type == HIGH_VALUE_MISMATCH],
        "suspicious_transactions": [{**row(a), "disclaimer": SUSPICIOUS_DISCLAIMER}
                                    for a in anomalies if a.anomaly_type == POTENTIALLY_SUSPICIOUS],
        "duplicate_groups": dup_groups,
        "investigation_summaries": [
            {"investigation_id": i.id, "anomaly_id": i.anomaly_id, "transaction_id": i.transaction_id,
             "conclusion": i.conclusion, "confidence": i.confidence, "explanation": i.explanation,
             "explanation_source": i.explanation_source, "steps": len(i.steps)} for i in invs],
        "disclaimer": "AuditFlow AI flags items for manual verification; it never confirms fraud.",
    }
    db.execute(delete(m.Report).where(m.Report.run_id == run_id, m.Report.format == "json"))
    db.add(m.Report(run_id=run_id, format="json", content=report))
    db.commit()
    return report


def build_report_csv(db: Session, run_id: str) -> str:
    _completed_run(db, run_id)
    anomalies = sorted(db.scalars(select(m.Anomaly).where(m.Anomaly.run_id == run_id)).all(),
                       key=lambda a: (SEVERITY_RANK.get(a.severity, 3), a.anomaly_type))
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["anomaly_id", "type", "severity", "status", "source", "date", "amount", "transaction_description",
                "reference", "related_date", "related_amount", "confidence", "description", "explanation"])
    for a in anomalies:
        t, r = a.transaction, a.related_transaction
        w.writerow([a.id, a.anomaly_type, a.severity, a.status, a.source, t.date.isoformat(), t.amount, t.raw_description,
                    t.reference or "", r.date.isoformat() if r else "", r.amount if r else "", a.confidence or "",
                    a.description, a.explanation or ""])
    return out.getvalue()
