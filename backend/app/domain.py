"""Internal domain model and constants (framework independent)."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

BANK, ACCOUNTING = "BANK", "ACCOUNTING"
DEBIT, CREDIT = "DEBIT", "CREDIT"

MATCHED, LIKELY_MATCH, REVIEW_REQUIRED, UNMATCHED = "MATCHED", "LIKELY_MATCH", "REVIEW_REQUIRED", "UNMATCHED"

MISSING_TRANSACTION = "MISSING_TRANSACTION"
DUPLICATE_TRANSACTION = "DUPLICATE_TRANSACTION"
TIMING_DIFFERENCE = "TIMING_DIFFERENCE"
AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
HIGH_VALUE_MISMATCH = "HIGH_VALUE_MISMATCH"
POTENTIALLY_SUSPICIOUS = "POTENTIALLY_SUSPICIOUS"
ANOMALY_TYPES = [MISSING_TRANSACTION, DUPLICATE_TRANSACTION, TIMING_DIFFERENCE, AMOUNT_MISMATCH,
                 HIGH_VALUE_MISMATCH, POTENTIALLY_SUSPICIOUS]

SUSPICIOUS_DISCLAIMER = "Potentially suspicious transaction requiring manual verification."


def new_id() -> str:
    return uuid.uuid4().hex


@dataclass
class Txn:
    id: str
    source: str
    date: date
    description: str
    amount: float  # always positive; direction is in transaction_type
    transaction_type: str
    debit: Optional[float] = None
    credit: Optional[float] = None
    reference: Optional[str] = None
    balance: Optional[float] = None
    currency: str = "INR"
    raw_description: str = ""
    normalized_description: str = ""
    normalized_reference: Optional[str] = None
    row_number: Optional[int] = None
    vendor_key: str = ""
    ref_keys: frozenset = field(default_factory=frozenset)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "source": self.source, "date": self.date.isoformat(), "description": self.description,
            "amount": self.amount, "transaction_type": self.transaction_type, "debit": self.debit,
            "credit": self.credit, "reference": self.reference, "balance": self.balance, "currency": self.currency,
            "raw_description": self.raw_description, "normalized_description": self.normalized_description,
            "row_number": self.row_number,
        }

    def brief(self) -> Dict[str, Any]:
        """Compact, evidence-style view (no internal ids) for investigations/LLM."""
        return {"source": self.source, "date": self.date.isoformat(), "amount": self.amount,
                "type": self.transaction_type, "description": self.raw_description or self.description,
                "reference": self.reference}


@dataclass
class MatchResult:
    bank_id: str
    accounting_id: Optional[str]
    score: float
    status: str
    level: Optional[int] = None
    signals: Dict[str, float] = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)
    date_diff_days: Optional[int] = None
    description_similarity: Optional[float] = None
    amount_difference: Optional[float] = None
    matched_by: str = "ENGINE"


@dataclass
class Anomaly:
    id: str
    transaction_id: str
    anomaly_type: str
    severity: str
    description: str
    source: str = BANK
    related_transaction_id: Optional[str] = None
    initial_type: Optional[str] = None
    confidence: Optional[float] = None
    details: Dict[str, Any] = field(default_factory=dict)
    status: str = "OPEN"
    explanation: Optional[str] = None
    explanation_source: Optional[str] = None
    investigation_id: Optional[str] = None

    def __post_init__(self):
        if self.initial_type is None:
            self.initial_type = self.anomaly_type


@dataclass
class DuplicateGroup:
    id: str
    source: str
    txn_ids: List[str]
    confidence: float
    explanation: str

