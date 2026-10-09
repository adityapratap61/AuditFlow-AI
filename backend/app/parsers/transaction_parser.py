"""Shared parsing primitives: flexible column recognition, row -> Txn conversion, parse errors/results."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.domain import Txn
from app.normalization.normalizer import build_transaction
from app.utils.text import normalize_description, vendor_key

SCANNED_PDF_MESSAGE = "Scanned/image-only PDF detected. OCR is not enabled in Phase 1."


class ParseError(Exception):
    status_code = 422
    code = "PARSE_ERROR"

    def __init__(self, message: str, details: Optional[list] = None):
        super().__init__(message)
        self.message = message
        self.details = details or []


class EmptyFileError(ParseError):
    status_code, code = 400, "EMPTY_FILE"


class MalformedFileError(ParseError):
    code = "MALFORMED_FILE"


class MissingColumnsError(ParseError):
    code = "MISSING_COLUMNS"


class NoTransactionsError(ParseError):
    code = "NO_TRANSACTIONS"


class ScannedPdfError(ParseError):
    code = "SCANNED_PDF"


@dataclass
class ParseResult:
    transactions: List[Txn]
    skipped_rows: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    file_type: str = "csv"
    total_rows: int = 0
    columns: Dict[str, str] = field(default_factory=dict)  # internal field -> header found in file


# ------------------------------------------------------------------ column recognition
ALIASES: Dict[str, List[str]] = {
    "date": ["date", "transaction date", "txn date", "trans date", "tran date", "posting date", "booking date",
             "voucher date", "entry date", "posted date", "trans dt", "txn dt"],
    "description": ["description", "narration", "particulars", "details", "transaction description", "remarks",
                    "transaction details", "memo", "narrative", "transaction remarks", "desc"],
    "vendor": ["vendor", "vendor name", "party", "party name", "payee", "supplier", "supplier name", "counterparty",
               "customer", "name", "beneficiary"],
    "debit": ["debit", "withdrawal", "debit amount", "withdrawals", "dr", "dr amount", "withdrawal amt", "debit amt",
              "paid out", "money out", "withdrawal amount", "debits"],
    "credit": ["credit", "deposit", "credit amount", "deposits", "cr", "cr amount", "deposit amt", "credit amt",
               "paid in", "money in", "deposit amount", "credits", "receipt"],
    "amount": ["amount", "transaction amount", "txn amount", "amt", "value", "net amount"],
    "reference": ["reference", "ref", "utr", "transaction id", "txn id", "reference number", "ref no", "ref number",
                  "chq no", "cheque no", "utr number", "utr no", "transaction ref", "reference no", "txn ref",
                  "transaction reference", "chq ref no", "cheque number"],
    "invoice": ["invoice number", "invoice no", "invoice", "bill no", "invoice id", "inv no", "bill number"],
    "balance": ["balance", "closing balance", "running balance", "available balance", "bal"],
    "currency": ["currency", "ccy", "curr"],
    "type": ["type", "dr cr", "cr dr", "transaction type", "txn type", "drcr", "debit credit"],
}
_FALLBACK = {"value date": "date", "date and time": "date"}
_LOOKUP: Dict[str, str] = {}
for _f, _names in ALIASES.items():
    for _n in _names:
        _LOOKUP.setdefault(_n, _f)
_MULTI = sorted(((a, f) for a, f in _LOOKUP.items() if " " in a), key=lambda x: -len(x[0]))


def norm_header(cell: Any) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(cell or "").lower())).strip()


def map_header(cells: Sequence[Any]) -> Dict[str, int]:
    """Map internal field names -> column index. Exact alias first, then token-subset, then fallbacks."""
    norm = [norm_header(c) for c in cells]
    mapping: Dict[str, int] = {}
    for i, n in enumerate(norm):
        f = _LOOKUP.get(n)
        if f and f not in mapping:
            mapping[f] = i
    for i, n in enumerate(norm):
        if not n or i in mapping.values():
            continue
        toks = set(n.split())
        for alias, f in _MULTI:
            if f not in mapping and set(alias.split()) <= toks:
                mapping[f] = i
                break
    for i, n in enumerate(norm):
        f = _FALLBACK.get(n)
        if f and f not in mapping:
            mapping[f] = i
    return mapping


def is_valid_mapping(m: Dict[str, int]) -> bool:
    return "date" in m and any(k in m for k in ("amount", "debit", "credit"))


def find_header_row(rows: Sequence[Sequence[Any]], max_scan: int = 3) -> Optional[Tuple[int, Dict[str, int]]]:
    for idx, row in enumerate(rows[:max_scan]):
        m = map_header(row)
        if is_valid_mapping(m):
            return idx, m
    return None


# ------------------------------------------------------------------ rows -> transactions
def _cell(row: Sequence[Any], mapping: Dict[str, int], key: str) -> Optional[str]:
    i = mapping.get(key)
    if i is None or i >= len(row) or row[i] is None:
        return None
    v = str(row[i]).strip()
    return v if v and v.lower() != "nan" else None


def rows_to_transactions(data: Sequence[Sequence[Any]], mapping: Dict[str, int], source: str,
                         start_row: int = 1) -> Tuple[List[Txn], List[Dict[str, Any]]]:
    txns: List[Txn] = []
    errors: List[Dict[str, Any]] = []
    for offset, row in enumerate(data):
        rn = start_row + offset
        if not any(str(c or "").strip() for c in row):
            continue
        date_v = _cell(row, mapping, "date")
        amounts = [_cell(row, mapping, k) for k in ("amount", "debit", "credit")]
        if date_v is None and not any(amounts):
            continue  # footer / label rows
        vendor, desc, inv = _cell(row, mapping, "vendor"), _cell(row, mapping, "description"), _cell(row, mapping, "invoice")
        parts = [p for p in (vendor, desc) if p]
        if inv and inv.lower() not in " ".join(parts).lower():
            parts.append(inv)
        raw = " ".join(" ".join(parts).split())
        try:
            t = build_transaction(
                source, date_v, raw, amount=amounts[0], debit=amounts[1], credit=amounts[2],
                reference=_cell(row, mapping, "reference"), balance=_cell(row, mapping, "balance"),
                currency=_cell(row, mapping, "currency"), row_number=rn, type_hint=_cell(row, mapping, "type"))
            if vendor:  # a dedicated vendor column is the cleanest signal for fuzzy matching
                t.normalized_description = normalize_description(vendor)
                t.vendor_key = vendor_key(t.normalized_description)
            txns.append(t)
        except ValueError as exc:
            errors.append({"row": rn, "error": str(exc)})
    return txns, errors
