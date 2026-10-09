"""SQLAlchemy ORM models."""
from __future__ import annotations

import datetime as dt
from typing import Any, List, Optional

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.domain import new_id


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class ReconciliationRun(Base):
    __tablename__ = "reconciliation_runs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    status: Mapped[str] = mapped_column(String(20), default="created", index=True)  # created|processing|completed|failed
    bank_filename: Mapped[Optional[str]] = mapped_column(String(200))
    bank_file_type: Mapped[Optional[str]] = mapped_column(String(10))
    accounting_filename: Mapped[Optional[str]] = mapped_column(String(200))
    summary: Mapped[Optional[dict]] = mapped_column(JSON)
    processing_time: Mapped[Optional[float]] = mapped_column(Float)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    completed_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime)
    transactions: Mapped[List["Transaction"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class Transaction(Base):
    __tablename__ = "transactions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("reconciliation_runs.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(12), index=True)  # BANK | ACCOUNTING
    date: Mapped[dt.date] = mapped_column(index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    amount: Mapped[float] = mapped_column(Float, index=True)
    transaction_type: Mapped[str] = mapped_column(String(10))
    debit: Mapped[Optional[float]] = mapped_column(Float)
    credit: Mapped[Optional[float]] = mapped_column(Float)
    reference: Mapped[Optional[str]] = mapped_column(String(100))
    balance: Mapped[Optional[float]] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    raw_description: Mapped[str] = mapped_column(Text, default="")
    normalized_description: Mapped[str] = mapped_column(Text, default="")
    normalized_reference: Mapped[Optional[str]] = mapped_column(String(100))
    row_number: Mapped[Optional[int]] = mapped_column(Integer)
    match_status: Mapped[Optional[str]] = mapped_column(String(20), index=True)
    matched_transaction_id: Mapped[Optional[str]] = mapped_column(String(32))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    run: Mapped[ReconciliationRun] = relationship(back_populates="transactions")
    __table_args__ = (Index("ix_txn_run_source", "run_id", "source"),)


class Match(Base):
    __tablename__ = "matches"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("reconciliation_runs.id", ondelete="CASCADE"), index=True)
    bank_transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.id", ondelete="CASCADE"))
    accounting_transaction_id: Mapped[Optional[str]] = mapped_column(ForeignKey("transactions.id", ondelete="CASCADE"))
    score: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(20), index=True)
    level: Mapped[Optional[int]] = mapped_column(Integer)
    signals: Mapped[Optional[dict]] = mapped_column(JSON)
    reasons: Mapped[Optional[list]] = mapped_column(JSON)
    date_diff_days: Mapped[Optional[int]] = mapped_column(Integer)
    description_similarity: Mapped[Optional[float]] = mapped_column(Float)
    amount_difference: Mapped[Optional[float]] = mapped_column(Float)
    matched_by: Mapped[str] = mapped_column(String(10), default="ENGINE")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    bank_transaction: Mapped[Transaction] = relationship(foreign_keys=[bank_transaction_id])
    accounting_transaction: Mapped[Optional[Transaction]] = relationship(foreign_keys=[accounting_transaction_id])


class Anomaly(Base):
    __tablename__ = "anomalies"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("reconciliation_runs.id", ondelete="CASCADE"), index=True)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.id", ondelete="CASCADE"), index=True)
    related_transaction_id: Mapped[Optional[str]] = mapped_column(ForeignKey("transactions.id", ondelete="SET NULL"))
    anomaly_type: Mapped[str] = mapped_column(String(30), index=True)
    initial_type: Mapped[Optional[str]] = mapped_column(String(30))
    severity: Mapped[str] = mapped_column(String(10), index=True)
    status: Mapped[str] = mapped_column(String(15), default="OPEN", index=True)  # OPEN | INVESTIGATED
    source: Mapped[str] = mapped_column(String(12), default="BANK")
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    description: Mapped[str] = mapped_column(Text, default="")
    details: Mapped[Optional[dict]] = mapped_column(JSON)
    explanation: Mapped[Optional[str]] = mapped_column(Text)
    explanation_source: Mapped[Optional[str]] = mapped_column(String(10))
    investigation_id: Mapped[Optional[str]] = mapped_column(String(32))  # latest investigation (logical reference)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    transaction: Mapped[Transaction] = relationship(foreign_keys=[transaction_id])
    related_transaction: Mapped[Optional[Transaction]] = relationship(foreign_keys=[related_transaction_id])


class Investigation(Base):
    __tablename__ = "investigations"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("reconciliation_runs.id", ondelete="CASCADE"), index=True)
    anomaly_id: Mapped[Optional[str]] = mapped_column(ForeignKey("anomalies.id", ondelete="SET NULL"), index=True)
    transaction_id: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(15), default="completed")
    conclusion: Mapped[Optional[str]] = mapped_column(String(30))
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    explanation: Mapped[Optional[str]] = mapped_column(Text)
    explanation_source: Mapped[Optional[str]] = mapped_column(String(10))
    explanation_detail: Mapped[Optional[dict]] = mapped_column(JSON)
    evidence: Mapped[Optional[dict]] = mapped_column(JSON)
    counterpart_transaction_id: Mapped[Optional[str]] = mapped_column(String(32))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    completed_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime)
    steps: Mapped[List["InvestigationStep"]] = relationship(
        back_populates="investigation", cascade="all, delete-orphan", order_by="InvestigationStep.step_number")


class InvestigationStep(Base):
    __tablename__ = "investigation_steps"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id", ondelete="CASCADE"), index=True)
    step_number: Mapped[int] = mapped_column(Integer)
    tool: Mapped[str] = mapped_column(String(50))
    arguments: Mapped[Optional[dict]] = mapped_column(JSON)
    result_summary: Mapped[str] = mapped_column(Text, default="")
    candidate_ids: Mapped[Optional[list]] = mapped_column(JSON)
    decision: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    investigation: Mapped[Investigation] = relationship(back_populates="steps")


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("reconciliation_runs.id", ondelete="CASCADE"), index=True)
    format: Mapped[str] = mapped_column(String(10), default="json")
    content: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
