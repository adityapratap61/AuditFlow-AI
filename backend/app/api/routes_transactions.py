import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.schemas import Page, TransactionDetail, TransactionOut
from app.services import transaction_service as svc

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.get("", response_model=Page[TransactionOut], summary="List/filter transactions")
def list_transactions(run_id: Optional[str] = None, source: Optional[str] = Query(None, description="BANK | ACCOUNTING"),
                      match_status: Optional[str] = Query(None, description="MATCHED | LIKELY_MATCH | REVIEW_REQUIRED | UNMATCHED"),
                      transaction_type: Optional[str] = Query(None, description="DEBIT | CREDIT"),
                      date_from: Optional[dt.date] = None, date_to: Optional[dt.date] = None,
                      min_amount: Optional[float] = Query(None, ge=0), max_amount: Optional[float] = Query(None, ge=0),
                      search: Optional[str] = Query(None, max_length=100),
                      limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    rows, total = svc.list_transactions(db, run_id=run_id, source=source, match_status=match_status,
                                        transaction_type=transaction_type, date_from=date_from, date_to=date_to,
                                        min_amount=min_amount, max_amount=max_amount, search=search,
                                        limit=limit, offset=offset)
    return Page[TransactionOut](items=[TransactionOut.model_validate(r) for r in rows], total=total, limit=limit, offset=offset)


@router.get("/{transaction_id}", response_model=TransactionDetail, summary="Transaction with its match and anomalies")
def get_transaction(transaction_id: str, db: Session = Depends(get_db)):
    return svc.get_transaction_detail(db, transaction_id)
