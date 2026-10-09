"""Transaction persistence helpers, ORM <-> domain conversion and queries."""
from __future__ import annotations

import datetime as dt
from typing import List, Optional, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.database import models as m
from app.database.schemas import AnomalyOut, MatchOut, TransactionDetail
from app.domain import Txn
from app.utils.text import reference_keys, vendor_key


def row_to_txn(r: m.Transaction) -> Txn:
    return Txn(
        id=r.id, source=r.source, date=r.date, description=r.description or "", amount=r.amount,
        transaction_type=r.transaction_type, debit=r.debit, credit=r.credit, reference=r.reference, balance=r.balance,
        currency=r.currency or "INR", raw_description=r.raw_description or "",
        normalized_description=r.normalized_description or "", normalized_reference=r.normalized_reference,
        row_number=r.row_number, vendor_key=vendor_key(r.normalized_description or ""),
        ref_keys=frozenset(reference_keys(r.raw_description, r.normalized_reference)))


def txn_to_row(run_id: str, t: Txn) -> m.Transaction:
    return m.Transaction(
        id=t.id, run_id=run_id, source=t.source, date=t.date, description=t.description, amount=t.amount,
        transaction_type=t.transaction_type, debit=t.debit, credit=t.credit, reference=t.reference, balance=t.balance,
        currency=t.currency, raw_description=t.raw_description, normalized_description=t.normalized_description,
        normalized_reference=t.normalized_reference, row_number=t.row_number)


def load_rows(db: Session, run_id: str, source: Optional[str] = None) -> List[m.Transaction]:
    stmt = select(m.Transaction).where(m.Transaction.run_id == run_id)
    if source:
        stmt = stmt.where(m.Transaction.source == source)
    return list(db.scalars(stmt.order_by(m.Transaction.date, m.Transaction.row_number)).all())


def list_transactions(db: Session, *, run_id: Optional[str] = None, source: Optional[str] = None,
                      match_status: Optional[str] = None, transaction_type: Optional[str] = None,
                      date_from: Optional[dt.date] = None, date_to: Optional[dt.date] = None,
                      min_amount: Optional[float] = None, max_amount: Optional[float] = None,
                      search: Optional[str] = None, limit: int = 50, offset: int = 0) -> Tuple[List[m.Transaction], int]:
    conds = []
    T = m.Transaction
    if run_id:
        conds.append(T.run_id == run_id)
    if source:
        conds.append(T.source == source.upper())
    if match_status:
        conds.append(T.match_status == match_status.upper())
    if transaction_type:
        conds.append(T.transaction_type == transaction_type.upper())
    if date_from:
        conds.append(T.date >= date_from)
    if date_to:
        conds.append(T.date <= date_to)
    if min_amount is not None:
        conds.append(T.amount >= min_amount)
    if max_amount is not None:
        conds.append(T.amount <= max_amount)
    if search:
        like = f"%{search.strip()}%"
        conds.append(or_(T.raw_description.ilike(like), T.reference.ilike(like)))
    total = db.scalar(select(func.count()).select_from(T).where(*conds)) or 0
    rows = db.scalars(select(T).where(*conds).order_by(T.date, T.row_number).limit(limit).offset(offset)).all()
    return list(rows), int(total)


def get_transaction_detail(db: Session, transaction_id: str) -> TransactionDetail:
    row = db.get(m.Transaction, transaction_id)
    if row is None:
        raise AppError(404, "TRANSACTION_NOT_FOUND", "Transaction not found.")
    detail = TransactionDetail.model_validate(row)
    match = db.scalars(select(m.Match).where(
        or_(m.Match.bank_transaction_id == row.id, m.Match.accounting_transaction_id == row.id))).first()
    if match is not None:
        detail.match = MatchOut.model_validate(match)
    anomalies = db.scalars(select(m.Anomaly).where(
        or_(m.Anomaly.transaction_id == row.id, m.Anomaly.related_transaction_id == row.id))).all()
    detail.anomalies = [AnomalyOut.model_validate(a) for a in anomalies]
    return detail
