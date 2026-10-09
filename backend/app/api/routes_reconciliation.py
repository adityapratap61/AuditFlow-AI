from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database import models as m
from app.database.database import get_db
from app.database.schemas import MatchOut, Page, ReconcileRequest, ReconciliationResponse, RunList
from app.services import reconciliation_service as svc

router = APIRouter(prefix="/api", tags=["reconciliation"])


@router.post("/reconcile", response_model=ReconciliationResponse, summary="Run reconciliation for an uploaded run")
def reconcile(req: ReconcileRequest, db: Session = Depends(get_db)):
    return svc.run_reconciliation(db, req.run_id, use_llm=req.use_llm)


@router.get("/reconciliation/{run_id}", response_model=ReconciliationResponse, summary="Run status, summary and anomalies")
def get_reconciliation(run_id: str, db: Session = Depends(get_db)):
    return svc.get_reconciliation(db, run_id)


@router.get("/reconciliations", response_model=RunList, summary="List reconciliation runs (newest first)")
def list_runs(limit: int = Query(20, ge=1, le=200), offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    return svc.list_runs(db, limit, offset)


@router.get("/matches", response_model=Page[MatchOut], summary="List match results with scoring detail")
def list_matches(run_id: Optional[str] = None, status: Optional[str] = None, matched_by: Optional[str] = None,
                 min_score: Optional[float] = Query(None, ge=0, le=100), max_score: Optional[float] = Query(None, ge=0, le=100),
                 limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    conds = []
    if run_id:
        conds.append(m.Match.run_id == run_id)
    if status:
        conds.append(m.Match.status == status.upper())
    if matched_by:
        conds.append(m.Match.matched_by == matched_by.upper())
    if min_score is not None:
        conds.append(m.Match.score >= min_score)
    if max_score is not None:
        conds.append(m.Match.score <= max_score)
    total = db.scalar(select(func.count()).select_from(m.Match).where(*conds)) or 0
    rows = db.scalars(select(m.Match).where(*conds).options(
        selectinload(m.Match.bank_transaction), selectinload(m.Match.accounting_transaction))
        .order_by(m.Match.score.desc(), m.Match.created_at).limit(limit).offset(offset)).all()
    return Page[MatchOut](items=[MatchOut.model_validate(r) for r in rows], total=int(total), limit=limit, offset=offset)
