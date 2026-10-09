"""On-demand and persisted agent investigations."""
from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.investigation import InvestigationResult, investigate
from app.agent.reconciliation_agent import apply_explanation
from app.agent.tools import InvestigationToolbox
from app.core.config import get_settings
from app.core.errors import AppError
from app.database import models as m
from app.database.schemas import InvestigationOut
from app.domain import ACCOUNTING, BANK, HIGH_VALUE_MISMATCH, POTENTIALLY_SUSPICIOUS, UNMATCHED
from app.llm.explainer import Explainer
from app.llm.ollama_client import get_ollama_client
from app.matching.matcher import TransactionIndex
from app.services.transaction_service import load_rows, row_to_txn


def to_json(v: Any) -> Any:
    return json.loads(json.dumps(v, default=str))


def persist_investigation(db: Session, run_id: str, anomaly_id: Optional[str], res: InvestigationResult) -> m.Investigation:
    inv = m.Investigation(
        id=res.id, run_id=run_id, anomaly_id=anomaly_id, transaction_id=res.transaction_id, status="completed",
        conclusion=res.conclusion, confidence=res.confidence, explanation=res.explanation,
        explanation_source=res.explanation_source, explanation_detail=to_json(res.explanation_detail),
        evidence=to_json(res.evidence), counterpart_transaction_id=res.counterpart.id if res.counterpart else None,
        completed_at=m.utcnow())
    for st in res.steps:
        inv.steps.append(m.InvestigationStep(
            step_number=st.step_number, tool=st.tool, arguments=to_json(st.arguments), result_summary=st.result_summary,
            candidate_ids=list(st.candidate_ids[:50]), decision=st.decision))
    db.add(inv)
    return inv


def investigate_anomaly(db: Session, anomaly_id: str, use_llm: bool = True) -> InvestigationOut:
    a = db.get(m.Anomaly, anomaly_id)
    if a is None:
        raise AppError(404, "ANOMALY_NOT_FOUND", "Anomaly not found.")
    s = get_settings()
    txns = [row_to_txn(r) for r in load_rows(db, a.run_id)]
    by_id = {t.id: t for t in txns}
    bank, acct = [t for t in txns if t.source == BANK], [t for t in txns if t.source == ACCOUNTING]
    txn = by_id.get(a.transaction_id)
    if txn is None:
        raise AppError(404, "TRANSACTION_NOT_FOUND", "The transaction for this anomaly no longer exists.")
    pair_of = {}
    for mt in db.scalars(select(m.Match).where(
            m.Match.run_id == a.run_id, m.Match.accounting_transaction_id.is_not(None), m.Match.status != UNMATCHED)):
        pair_of[mt.bank_transaction_id] = mt.accounting_transaction_id
        pair_of[mt.accounting_transaction_id] = mt.bank_transaction_id
    opp_src = ACCOUNTING if txn.source == BANK else BANK
    own = pair_of.get(txn.id)
    taken = {i for i in pair_of if i != own and i in by_id and by_id[i].source == opp_src}
    opposite, same = (acct, bank) if txn.source == BANK else (bank, acct)
    tb = InvestigationToolbox(s, TransactionIndex(opposite), TransactionIndex(same), taken)
    res = investigate(txn, tb, s)
    siblings = list(db.scalars(select(m.Anomaly).where(m.Anomaly.run_id == a.run_id,
                                                       m.Anomaly.transaction_id == a.transaction_id)).all())
    flags = [x.anomaly_type for x in siblings if x.anomaly_type in (HIGH_VALUE_MISMATCH, POTENTIALLY_SUSPICIOUS)]
    apply_explanation(res, Explainer(s, get_ollama_client(), use_llm=use_llm), flags)
    inv = persist_investigation(db, a.run_id, a.id, res)
    db.flush()
    for x in siblings:
        x.investigation_id, x.status = inv.id, "INVESTIGATED"
        x.explanation, x.explanation_source = res.explanation, res.explanation_source
    db.commit()
    return InvestigationOut.model_validate(inv)


def get_investigation(db: Session, investigation_id: str) -> InvestigationOut:
    inv = db.get(m.Investigation, investigation_id)
    if inv is None:
        raise AppError(404, "INVESTIGATION_NOT_FOUND", "Investigation not found.")
    return InvestigationOut.model_validate(inv)


def list_investigations(db: Session, run_id: Optional[str], anomaly_id: Optional[str], limit: int, offset: int):
    stmt = select(m.Investigation)
    if run_id:
        stmt = stmt.where(m.Investigation.run_id == run_id)
    if anomaly_id:
        stmt = stmt.where(m.Investigation.anomaly_id == anomaly_id)
    rows = db.scalars(stmt.order_by(m.Investigation.created_at.desc()).limit(limit).offset(offset)).all()
    return [InvestigationOut.model_validate(r) for r in rows]
