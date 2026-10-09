"""Build normalised internal transactions from raw field values."""
from __future__ import annotations

from typing import Any, Optional

from app.domain import CREDIT, DEBIT, Txn, new_id
from app.utils.amounts import parse_amount
from app.utils.dates import parse_date
from app.utils.text import normalize_description, normalize_reference, reference_keys, vendor_key

_DEBIT_HINTS = ("dr", "debit", "withdrawal", "payment", "paid", "expense", "out")
_CREDIT_HINTS = ("cr", "credit", "deposit", "receipt", "received", "income", "in")


def finalize(txn: Txn) -> Txn:
    """(Re)compute derived/normalised fields. Never touches raw_description."""
    txn.normalized_description = normalize_description(txn.raw_description or txn.description)
    txn.normalized_reference = normalize_reference(txn.reference)
    txn.vendor_key = vendor_key(txn.normalized_description)
    txn.ref_keys = frozenset(reference_keys(txn.raw_description, txn.normalized_reference))
    return txn


def _hint_type(hint: Optional[str]) -> Optional[str]:
    if not hint:
        return None
    h = str(hint).strip().lower()
    if h in _DEBIT_HINTS:
        return DEBIT
    if h in _CREDIT_HINTS:
        return CREDIT
    return None


def build_transaction(source: str, date_val: Any, description: Any, *, amount: Any = None, debit: Any = None,
                      credit: Any = None, reference: Any = None, balance: Any = None, currency: Optional[str] = None,
                      row_number: Optional[int] = None, type_hint: Optional[str] = None,
                      txn_id: Optional[str] = None) -> Txn:
    """Create a Txn. Raises ValueError on invalid date/amount or missing amount."""
    d = parse_date(date_val)
    raw = "" if description is None or str(description).strip().lower() == "nan" else str(description)
    dv, cv, av = parse_amount(debit), parse_amount(credit), parse_amount(amount)
    dv = dv if dv else None  # zero -> None
    cv = cv if cv else None
    if dv is not None and cv is not None:
        raise ValueError("Both debit and credit are populated")
    if dv is not None:
        ttype, amt = DEBIT, abs(dv)
    elif cv is not None:
        ttype, amt = CREDIT, abs(cv)
    elif av:
        ttype = _hint_type(type_hint) or (DEBIT if av < 0 else CREDIT)
        amt = abs(av)
    else:
        raise ValueError("Missing or zero amount")
    ref = None if reference is None or str(reference).strip().lower() in {"", "nan", "none"} else str(reference).strip()
    txn = Txn(
        id=txn_id or new_id(), source=source, date=d, description=" ".join(raw.split()), amount=round(amt, 2),
        transaction_type=ttype, debit=round(amt, 2) if ttype == DEBIT else None,
        credit=round(amt, 2) if ttype == CREDIT else None, reference=ref, balance=parse_amount(balance),
        currency=(str(currency).strip().upper() if currency and str(currency).strip().lower() != "nan" else "INR"),
        raw_description=raw, row_number=row_number,
    )
    return finalize(txn)
