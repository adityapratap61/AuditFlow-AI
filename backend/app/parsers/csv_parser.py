"""Robust CSV parser for bank statements and accounting exports (flexible headers, delimiters, encodings)."""
from __future__ import annotations

import csv
import io
import logging
from typing import List

from app.domain import Txn
from app.parsers.transaction_parser import (EmptyFileError, MalformedFileError, MissingColumnsError, NoTransactionsError,
                                            ParseResult, find_header_row, map_header, rows_to_transactions)

log = logging.getLogger(__name__)


def _decode(content: bytes) -> str:
    for enc in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
        try:
            return content.decode(enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise MalformedFileError("Unable to decode the file as text.")


def parse_csv(content: bytes, source: str) -> ParseResult:
    if not content or not content.strip():
        raise EmptyFileError("The uploaded file is empty.")
    if b"\x00" in content[:4096] and content[:2] not in (b"\xff\xfe", b"\xfe\xff") or content.lstrip()[:5] == b"%PDF-":
        raise MalformedFileError("The file does not look like a text CSV.")
    text = _decode(content)
    try:
        sniffed = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|").delimiter
    except csv.Error:
        sniffed = ","
    rows: List[List[str]] = []
    found = None
    for delimiter in dict.fromkeys([sniffed, ",", ";", "\t", "|"]):  # first delimiter that yields a valid header wins
        try:
            candidate = [r for r in csv.reader(io.StringIO(text), delimiter=delimiter)]
        except csv.Error as exc:
            if delimiter == sniffed:
                raise MalformedFileError(f"Malformed CSV: {exc}")
            continue
        rows = rows or candidate
        found = find_header_row(candidate, max_scan=15)
        if found:
            rows = candidate
            break
    if not any(any(c.strip() for c in r) for r in rows):
        raise EmptyFileError("The uploaded file is empty.")
    if not found:
        best = max(rows[:15], key=lambda r: len(map_header(r)), default=[])
        m = map_header(best)
        missing = (["date"] if "date" not in m else []) + (
            ["amount (or debit/credit)"] if not any(k in m for k in ("amount", "debit", "credit")) else [])
        raise MissingColumnsError("Missing required column(s): " + ", ".join(missing or ["date", "amount"]) + ".",
                                  [{"detected_columns": [c for c in best if c.strip()]}])
    idx, mapping = found
    header = rows[idx]
    txns, errors = rows_to_transactions(rows[idx + 1:], mapping, source, start_row=idx + 2)
    if not txns:
        raise NoTransactionsError("No valid transaction rows were found in the CSV.", errors[:20])
    warnings: List[str] = []
    if "description" not in mapping and "vendor" not in mapping:
        warnings.append("No description/vendor column recognised; matching will rely on amount, date and reference.")
    if errors:
        warnings.append(f"{len(errors)} row(s) skipped due to invalid data.")
    log.info("Parsed CSV source=%s rows=%d transactions=%d skipped=%d", source, len(rows) - idx - 1, len(txns), len(errors))
    return ParseResult(transactions=txns, skipped_rows=errors, warnings=warnings, file_type="csv",
                       total_rows=len(txns) + len(errors),
                       columns={k: header[i] for k, i in mapping.items() if i < len(header)})
