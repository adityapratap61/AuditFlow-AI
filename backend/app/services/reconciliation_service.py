"""Upload persistence and the end-to-end reconciliation pipeline (match -> anomalies -> agent -> persist)."""
from __future__ import annotations

import logging
import time
from collections import Counter
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.agent.reconciliation_agent import ReconciliationAgent
from app.anomaly.detector import detect_anomalies
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.database import models as m
from app.database.schemas import AnomalyOut, ReconciliationResponse, RunList, UploadResponse
from app.domain import (ACCOUNTING, BANK, HIGH_VALUE_MISMATCH, LIKELY_MATCH, MATCHED, POTENTIALLY_SUSPICIOUS,
                        REVIEW_REQUIRED, UNMATCHED, Anomaly, DuplicateGroup, MatchResult, Txn)
from app.llm.explainer import Explainer
from app.llm.ollama_client import get_ollama_client
from app.matching.matcher import Matcher
from app.parsers.transaction_parser import ParseResult
from app.services.anomaly_service import SEVERITY_RANK, count_by_type
from app.services.investigation_service import persist_investigation, to_json
from app.services.transaction_service import load_rows, row_to_txn, txn_to_row

log = logging.getLogger(__name__)
_PRIVATE_KEYS = ("narrative", "narrative_source", "overall_status")


# ------------------------------------------------------------------ runs & uploads
def get_run(db: Session, run_id: str) -> m.ReconciliationRun:
    run = db.get(m.ReconciliationRun, run_id)
    if run is None:
        raise AppError(404, "RUN_NOT_FOUND", "Reconciliation run not found.")
    return run


def reset_results(db: Session, run_id: str) -> None:
    """Remove derived results (keeps uploaded transactions)."""
    for model in (m.Investigation, m.Anomaly, m.Match, m.Report):
        db.execute(delete(model).where(model.run_id == run_id))
    db.execute(update(m.Transaction).where(m.Transaction.run_id == run_id)
               .values(match_status=None, matched_transaction_id=None))


def store_upload(db: Session, run_id: Optional[str], source: str, result: ParseResult, filename: str,
                 file_type: str) -> UploadResponse:
    run = get_run(db, run_id) if run_id else None
    if run is None:
        run = m.ReconciliationRun(status="created")
        db.add(run)
        db.flush()
    if run.status == "processing":
        raise AppError(409, "RUN_BUSY", "This reconciliation run is currently processing.")
    reset_results(db, run.id)
    db.execute(delete(m.Transaction).where(m.Transaction.run_id == run.id, m.Transaction.source == source))
    db.add_all([txn_to_row(run.id, t) for t in result.transactions])
    if source == BANK:
        run.bank_filename, run.bank_file_type = filename, file_type
    else:
        run.accounting_filename = filename
    db.flush()
    counts = dict(db.execute(select(m.Transaction.source, func.count()).where(m.Transaction.run_id == run.id)
                             .group_by(m.Transaction.source)).all())
    bank_up, acct_up = counts.get(BANK, 0) > 0, counts.get(ACCOUNTING, 0) > 0
    run.status, run.summary, run.error_message, run.completed_at, run.processing_time = (
        "ready" if bank_up and acct_up else "created", None, None, None, None)
    db.commit()
    log.info("Upload stored run=%s source=%s type=%s transactions=%d skipped=%d", run.id, source, file_type,
             len(result.transactions), len(result.skipped_rows))
    return UploadResponse(
        run_id=run.id, source=source, filename=filename, file_type=file_type,
        transactions_extracted=len(result.transactions), skipped_rows=len(result.skipped_rows),
        parse_errors=result.skipped_rows[:50], warnings=result.warnings, run_status=run.status,
        bank_uploaded=bank_up, accounting_uploaded=acct_up, ready_to_reconcile=bank_up and acct_up)


# ------------------------------------------------------------------ summary
def overall_status(summary: Dict[str, Any]) -> str:
    if summary["high_risk"] > 0:
        return "ATTENTION_REQUIRED"
    if summary["total_anomalies"] > 0 or summary["review_required"] or summary["unmatched"]:
        return "REVIEW_NEEDED"
    return "RECONCILED"


def compute_summary(bank: Sequence[Txn], accounting: Sequence[Txn], matches: Sequence[MatchResult],
                    anomalies: Sequence[Anomaly], groups: Sequence[DuplicateGroup]) -> Dict[str, Any]:
    st = Counter(mr.status for mr in matches)
    paired_acct = {mr.accounting_id for mr in matches if mr.accounting_id and mr.status != UNMATCHED}
    by_type = count_by_type(a.anomaly_type for a in anomalies)
    n_bank = len(bank)
    return {
        "total_bank_transactions": n_bank, "total_accounting_transactions": len(accounting),
        "matched": st.get(MATCHED, 0), "likely_matches": st.get(LIKELY_MATCH, 0),
        "review_required": st.get(REVIEW_REQUIRED, 0), "unmatched": st.get(UNMATCHED, 0),
        "unmatched_accounting": sum(1 for t in accounting if t.id not in paired_acct),
        "match_rate": round((st.get(MATCHED, 0) + st.get(LIKELY_MATCH, 0)) / n_bank, 4) if n_bank else 0.0,
        "total_anomalies": len(anomalies), "high_risk": sum(1 for a in anomalies if a.severity == "HIGH"),
        "anomaly_counts": by_type, "high_value_mismatches": by_type[HIGH_VALUE_MISMATCH],
        "suspicious_transactions": by_type[POTENTIALLY_SUSPICIOUS], "duplicate_groups": len(groups),
        "duplicate_group_details": [{"id": g.id, "source": g.source, "transaction_ids": g.txn_ids,
                                     "confidence": g.confidence, "explanation": g.explanation} for g in groups],
    }


# ------------------------------------------------------------------ pipeline
def _persist(db: Session, run: m.ReconciliationRun, bank_rows, acct_rows, matches: List[MatchResult],
             anomalies: List[Anomaly], investigations, primary: Dict[str, str]) -> None:
    rows = {r.id: r for r in [*bank_rows, *acct_rows]}
    for r in rows.values():
        r.match_status, r.matched_transaction_id = UNMATCHED, None
    for mr in matches:
        paired = bool(mr.accounting_id) and mr.status != UNMATCHED
        db.add(m.Match(
            run_id=run.id, bank_transaction_id=mr.bank_id, accounting_transaction_id=mr.accounting_id if paired else None,
            score=mr.score, status=mr.status, level=mr.level, signals=to_json(mr.signals), reasons=list(mr.reasons),
            date_diff_days=mr.date_diff_days, description_similarity=mr.description_similarity,
            amount_difference=mr.amount_difference, matched_by=mr.matched_by))
        if paired:
            rows[mr.bank_id].match_status = rows[mr.accounting_id].match_status = mr.status
            rows[mr.bank_id].matched_transaction_id, rows[mr.accounting_id].matched_transaction_id = mr.accounting_id, mr.bank_id
    for a in anomalies:
        db.add(m.Anomaly(
            id=a.id, run_id=run.id, transaction_id=a.transaction_id, related_transaction_id=a.related_transaction_id,
            anomaly_type=a.anomaly_type, initial_type=a.initial_type, severity=a.severity, status=a.status,
            source=a.source, confidence=a.confidence, description=a.description, details=to_json(a.details),
            explanation=a.explanation, explanation_source=a.explanation_source, investigation_id=a.investigation_id))
    db.flush()  # anomalies must exist before investigations reference them
    for res in investigations:
        persist_investigation(db, run.id, primary.get(res.id), res)
    db.flush()


def run_reconciliation(db: Session, run_id: str, use_llm: bool = True) -> ReconciliationResponse:
    s: Settings = get_settings()
    run = get_run(db, run_id)
    if run.status == "processing":
        raise AppError(409, "RUN_BUSY", "This reconciliation run is already processing.")
    bank_rows, acct_rows = load_rows(db, run_id, BANK), load_rows(db, run_id, ACCOUNTING)
    if not bank_rows or not acct_rows:
        raise AppError(409, "RUN_NOT_READY", "Upload both a bank statement and an accounting CSV before reconciling.")
    run.status, run.error_message = "processing", None
    db.commit()
    t0 = time.perf_counter()
    log.info("Reconciliation started run=%s bank=%d accounting=%d", run_id, len(bank_rows), len(acct_rows))
    try:
        reset_results(db, run_id)
        bank, acct = [row_to_txn(r) for r in bank_rows], [row_to_txn(r) for r in acct_rows]
        matches = Matcher(s).match(bank, acct)
        anomalies, groups = detect_anomalies(bank, acct, matches, s)
        log.info("Initial pass: matched=%d anomalies=%d", sum(1 for x in matches if x.status == MATCHED), len(anomalies))
        explainer = Explainer(s, get_ollama_client(), use_llm=use_llm)
        outcome = ReconciliationAgent(s, bank, acct, matches, anomalies, explainer).run()
        summary = compute_summary(bank, acct, outcome.matches, outcome.anomalies, groups)
        summary["overall_status"] = overall_status(summary)
        narrative, nsrc = explainer.summarize({k: v for k, v in summary.items() if k != "duplicate_group_details"})
        summary["narrative"], summary["narrative_source"] = narrative, nsrc
        _persist(db, run, bank_rows, acct_rows, outcome.matches, outcome.anomalies, outcome.investigations,
                 outcome.primary_anomaly)
        run.summary = to_json(summary)
        run.processing_time = round(time.perf_counter() - t0, 3)
        run.status, run.completed_at = "completed", m.utcnow()
        db.commit()
    except AppError:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        log.exception("Reconciliation failed run=%s", run_id)
        failed = db.get(m.ReconciliationRun, run_id)
        if failed is not None:
            failed.status, failed.error_message = "failed", f"Internal error ({type(exc).__name__})"
            db.commit()
        raise AppError(500, "RECONCILIATION_FAILED", "Reconciliation failed due to an internal error.")
    log.info("Reconciliation completed run=%s matched=%d likely=%d review=%d unmatched=%d anomalies=%d time=%.2fs",
             run_id, summary["matched"], summary["likely_matches"], summary["review_required"], summary["unmatched"],
             summary["total_anomalies"], run.processing_time)
    return get_reconciliation(db, run_id)


# ------------------------------------------------------------------ read models
def _response(db: Session, run: m.ReconciliationRun, with_anomalies: bool = True) -> ReconciliationResponse:
    summary = dict(run.summary) if run.summary else None
    extra = {k: summary.pop(k, None) for k in _PRIVATE_KEYS} if summary else {}
    anomalies: List[AnomalyOut] = []
    if with_anomalies and run.status == "completed":
        rows = list(db.scalars(select(m.Anomaly).where(m.Anomaly.run_id == run.id)).all())
        rows.sort(key=lambda a: (SEVERITY_RANK.get(a.severity, 3), a.anomaly_type, a.created_at))
        anomalies = [AnomalyOut.model_validate(a) for a in rows]
    return ReconciliationResponse(
        run_id=run.id, status=run.status, overall_status=extra.get("overall_status"), summary=summary,
        anomalies=anomalies, processing_time=run.processing_time, narrative=extra.get("narrative"),
        bank_filename=run.bank_filename, accounting_filename=run.accounting_filename, created_at=run.created_at,
        completed_at=run.completed_at, error=run.error_message)


def get_reconciliation(db: Session, run_id: str) -> ReconciliationResponse:
    return _response(db, get_run(db, run_id))


def list_runs(db: Session, limit: int, offset: int) -> RunList:
    total = db.scalar(select(func.count()).select_from(m.ReconciliationRun)) or 0
    runs = db.scalars(select(m.ReconciliationRun).order_by(m.ReconciliationRun.created_at.desc())
                      .limit(limit).offset(offset)).all()
    return RunList(items=[_response(db, r, with_anomalies=False) for r in runs], total=int(total), limit=limit, offset=offset)
