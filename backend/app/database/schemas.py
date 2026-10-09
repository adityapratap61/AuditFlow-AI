"""Pydantic request/response schemas (the contract for the Phase 2 frontend)."""
from __future__ import annotations

import datetime as dt
from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody


class Page(BaseModel, Generic[T]):
    items: List[T]
    total: int
    limit: int
    offset: int


class HealthResponse(BaseModel):
    status: str
    database: str
    ollama: str
    service: str = "AuditFlow AI"
    tagline: str = "Reconcile. Investigate. Resolve."
    version: str = ""


class UploadResponse(BaseModel):
    run_id: str
    source: str
    filename: str
    file_type: str
    transactions_extracted: int
    skipped_rows: int
    parse_errors: List[Dict[str, Any]] = []
    warnings: List[str] = []
    run_status: str
    bank_uploaded: bool
    accounting_uploaded: bool
    ready_to_reconcile: bool


class ReconcileRequest(BaseModel):
    run_id: str
    use_llm: bool = Field(True, description="Use Ollama for explanations when available.")


class TransactionOut(ORM):
    id: str
    run_id: str
    source: str
    date: dt.date
    description: str
    amount: float
    transaction_type: str
    debit: Optional[float] = None
    credit: Optional[float] = None
    reference: Optional[str] = None
    balance: Optional[float] = None
    currency: str
    raw_description: str
    normalized_description: str
    row_number: Optional[int] = None
    match_status: Optional[str] = None
    matched_transaction_id: Optional[str] = None


class MatchOut(ORM):
    id: str
    run_id: str
    bank_transaction_id: str
    accounting_transaction_id: Optional[str] = None
    score: float
    status: str
    level: Optional[int] = None
    signals: Optional[Dict[str, Any]] = None
    reasons: Optional[List[str]] = None
    date_diff_days: Optional[int] = None
    description_similarity: Optional[float] = None
    amount_difference: Optional[float] = None
    matched_by: str
    bank_transaction: Optional[TransactionOut] = None
    accounting_transaction: Optional[TransactionOut] = None


class AnomalyOut(ORM):
    id: str
    run_id: str
    transaction_id: str
    related_transaction_id: Optional[str] = None
    anomaly_type: str
    initial_type: Optional[str] = None
    severity: str
    status: str
    source: str
    confidence: Optional[float] = None
    description: str
    details: Optional[Dict[str, Any]] = None
    explanation: Optional[str] = None
    explanation_source: Optional[str] = None
    investigation_id: Optional[str] = None
    created_at: dt.datetime


class AnomalyDetail(AnomalyOut):
    transaction: Optional[TransactionOut] = None
    related_transaction: Optional[TransactionOut] = None


class TransactionDetail(TransactionOut):
    match: Optional[MatchOut] = None
    anomalies: List[AnomalyOut] = []


class InvestigationStepOut(ORM):
    id: str
    step_number: int
    tool: str
    arguments: Optional[Dict[str, Any]] = None
    result_summary: str
    candidate_ids: Optional[List[str]] = None
    decision: Optional[str] = None
    created_at: dt.datetime


class InvestigationOut(ORM):
    id: str
    run_id: str
    anomaly_id: Optional[str] = None
    transaction_id: str
    status: str
    conclusion: Optional[str] = None
    confidence: Optional[float] = None
    explanation: Optional[str] = None
    explanation_source: Optional[str] = None
    explanation_detail: Optional[Dict[str, Any]] = None
    evidence: Optional[Dict[str, Any]] = None
    counterpart_transaction_id: Optional[str] = None
    created_at: dt.datetime
    completed_at: Optional[dt.datetime] = None
    steps: List[InvestigationStepOut] = []


class ReconciliationResponse(BaseModel):
    run_id: str
    status: str
    overall_status: Optional[str] = None
    summary: Optional[Dict[str, Any]] = None
    anomalies: List[AnomalyOut] = []
    processing_time: Optional[float] = None
    narrative: Optional[str] = None
    bank_filename: Optional[str] = None
    accounting_filename: Optional[str] = None
    created_at: Optional[dt.datetime] = None
    completed_at: Optional[dt.datetime] = None
    error: Optional[str] = None


class InvestigateRequest(BaseModel):
    use_llm: bool = Field(True, description="Use Ollama to phrase the explanation when available.")


class RunList(BaseModel):
    items: List[ReconciliationResponse]
    total: int
    limit: int
    offset: int
