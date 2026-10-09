"""Bank statement PDF parser (text-based PDFs only; OCR is out of scope for Phase 1).

Strategy: (1) table extraction via pdfplumber, (2) generic line-based parsing of text extracted by
PyMuPDF (fitz) or pdfplumber. The result with more transactions wins. Bank-specific parsers can be
plugged in with `register_bank_parser`.
"""
from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from app.domain import BANK, Txn
from app.normalization.normalizer import build_transaction
from app.parsers.transaction_parser import (SCANNED_PDF_MESSAGE, MalformedFileError, NoTransactionsError, ParseError,
                                            ParseResult, ScannedPdfError, find_header_row, rows_to_transactions)
from app.utils.amounts import parse_amount
from app.utils.dates import DATE_RE, match_date_at_start

log = logging.getLogger(__name__)

# ---------------------------------------------------------------- bank-specific plug-in registry
BankParser = Callable[[List[List[str]], str], ParseResult]
_BANK_PARSERS: List[Tuple[str, Callable[[str], bool], BankParser]] = []


def register_bank_parser(name: str, detector: Callable[[str], bool], parser: BankParser) -> None:
    """Register a bank-specific parser. `detector(full_text)` decides applicability;
    `parser(pages_lines, source)` returns a ParseResult."""
    _BANK_PARSERS.append((name, detector, parser))


# ---------------------------------------------------------------- text extraction
def _lines_from_words(words: Sequence[Tuple[float, float, float, float, str]], tol: float = 3.0) -> List[str]:
    rows: List[List[Tuple[float, float, str]]] = []
    centers: List[float] = []
    for x0, y0, x1, y1, w in sorted(words, key=lambda t: (t[1], t[0])):
        yc = (y0 + y1) / 2
        if centers and abs(yc - centers[-1]) <= tol:
            rows[-1].append((x0, yc, w))
        else:
            rows.append([(x0, yc, w)])
            centers.append(yc)
    return [" ".join(w for _, _, w in sorted(r)) for r in rows]


def _extract_pages_lines(content: bytes) -> List[List[str]]:
    try:
        import fitz  # PyMuPDF
    except ImportError:
        fitz = None
    if fitz is not None:
        try:
            doc = fitz.open(stream=content, filetype="pdf")
            if getattr(doc, "needs_pass", False):
                raise MalformedFileError("The PDF is password protected.")
            pages = []
            for page in doc:
                words = [(w[0], w[1], w[2], w[3], w[4]) for w in page.get_text("words")]
                pages.append(_lines_from_words(words))
            doc.close()
            return pages
        except ParseError:
            raise
        except Exception as exc:  # corrupt file
            log.warning("PyMuPDF failed (%s); trying pdfplumber", type(exc).__name__)
    try:
        import pdfplumber
    except ImportError:
        raise MalformedFileError("No PDF engine available (install PyMuPDF or pdfplumber).")
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            return [(p.extract_text(x_tolerance=2, y_tolerance=3) or "").splitlines() for p in pdf.pages]
    except Exception as exc:
        raise MalformedFileError(f"Unreadable PDF ({type(exc).__name__}).")


def _extract_tables(content: bytes) -> List[List[List[str]]]:
    try:
        import pdfplumber
    except ImportError:
        return []
    out: List[List[List[str]]] = []
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                for tb in page.extract_tables() or []:
                    out.append([["" if c is None else str(c) for c in row] for row in tb])
    except Exception as exc:
        log.info("Table extraction failed: %s", type(exc).__name__)
    return out


# ---------------------------------------------------------------- table path
def _merge_continuations(rows: List[List[str]], m: Dict[str, int]) -> List[List[str]]:
    di, ni = m.get("date"), m.get("description", m.get("vendor"))
    out: List[List[str]] = []
    for r in rows:
        r = list(r)
        no_amount = not any((r[m[k]].strip() if m.get(k) is not None and m[k] < len(r) else "")
                            for k in ("amount", "debit", "credit"))
        if out and di is not None and di < len(r) and not r[di].strip() and no_amount and ni is not None \
                and ni < len(r) and r[ni].strip():
            out[-1][ni] = (out[-1][ni] + " " + r[ni]).strip()
            continue
        out.append(r)
    return out


def _parse_tables(tables: List[List[List[str]]], source: str) -> Tuple[List[Txn], List[dict]]:
    txns: List[Txn] = []
    errors: List[dict] = []
    mapping: Optional[Dict[str, int]] = None
    ncols = 0
    counter = 1
    for rows in tables:
        found = find_header_row(rows, max_scan=3)
        if found:
            idx, mapping = found
            ncols = len(rows[idx])
            data = rows[idx + 1:]
        elif mapping and rows and len(rows[0]) == ncols:
            data = rows
        else:
            continue
        data = _merge_continuations(data, mapping)
        t, e = rows_to_transactions(data, mapping, source, start_row=counter)
        counter += len(data)
        txns.extend(t)
        errors.extend(e)
    return txns, errors


# ---------------------------------------------------------------- text path
_AMT = (r"(?:₹|Rs\.?|INR)?\s?\(?-?(?:\d{1,3}(?:,\d{2,3})+(?:\.\d{1,2})?|\d+\.\d{1,2})\)?"
        r"(?:\s?(?:Dr|Cr|DR|CR)\b\.?)?")
_TRAIL = re.compile(rf"((?:\s+{_AMT})+)\s*$")
_AMT_TOKEN = re.compile(_AMT)
_HEADER_WORDS = ("date", "narration", "description", "particulars", "details", "debit", "credit", "withdrawal",
                 "deposit", "balance", "amount", "chq", "ref")
_FOOTER = re.compile(r"(?i)^(page\s+\d+|.*\bpage\s+\d+\s+of\s+\d+|statement\b|closing balance|total\b|grand total|"
                     r"account\b|customer\b|branch\b|ifsc|generated|this is a computer|end of statement|continued|"
                     r"registered office|opening balance)")
_OPENING = re.compile(rf"(?i)opening\s+balance[^0-9\-\(]*({_AMT})")
_REF_RE = re.compile(r"(?i)\b(?:UTR|RRN|REF(?:ERENCE)?|TXN(?:\s?ID)?|CHQ(?:\s?NO)?)[\s.:#/-]*([A-Za-z0-9]{6,})\b")
_REF_FALLBACK = re.compile(r"\b([A-Z]{3,6}[A-Z0-9]*\d{8,}|\d{12,16})\b")
_DEBIT_WORDS = re.compile(r"(?i)\b(withdraw\w*|debit|paid|payment|purchase|atm|pos|chq|cheque|charges?|fee|emi|"
                          r"imps out|neft out|bill|tds|gst)\b")
_CREDIT_WORDS = re.compile(r"(?i)\b(deposit\w*|credit|salary|received|refund|interest|inward|neft in|imps in|"
                           r"cash dep\w*|receipt)\b")


@dataclass
class _Entry:
    date: object
    desc: str
    amounts: List[str]
    closed: bool = False


@dataclass
class _Hint:
    has_balance: bool = True
    has_debit_credit: bool = False
    credit_first: bool = False


def _header_hint(line: str) -> Optional[_Hint]:
    low = line.lower()
    if sum(1 for w in _HEADER_WORDS if w in low) < 3 or match_date_at_start(line):
        return None
    d = min([low.find(k) for k in ("debit", "withdrawal") if k in low] or [-1])
    c = min([low.find(k) for k in ("credit", "deposit") if k in low] or [-1])
    return _Hint(has_balance="balance" in low, has_debit_credit=d >= 0 and c >= 0,
                 credit_first=d >= 0 and c >= 0 and c < d)


def _split_amounts(rest: str) -> Tuple[str, List[str]]:
    m = _TRAIL.search(rest)
    if not m:
        return rest.strip(), []
    return rest[:m.start()].strip(), [t.strip() for t in _AMT_TOKEN.findall(m.group(1))]


def _guess_direction(desc: str) -> Optional[str]:
    d, c = bool(_DEBIT_WORDS.search(desc)), bool(_CREDIT_WORDS.search(desc))
    if d and not c:
        return "DEBIT"
    if c and not d:
        return "CREDIT"
    return None


def _extract_reference(desc: str) -> Optional[str]:
    m = _REF_RE.search(desc) or _REF_FALLBACK.search(desc)
    return m.group(1) if m else None


def parse_text_lines(pages_lines: List[List[str]], source: str = BANK) -> Tuple[List[Txn], List[dict], List[str]]:
    entries: List[_Entry] = []
    hint = _Hint()
    opening: Optional[float] = None
    errors: List[dict] = []
    warnings: List[str] = []
    prev: Optional[_Entry] = None
    for lines in pages_lines:
        prev = None  # never continue a description across a page break
        for raw in lines:
            s = raw.strip()
            if not s:
                continue
            h = _header_hint(s)
            if h:
                hint, prev = h, None
                continue
            md = match_date_at_start(s)
            if md:
                d, end = md
                rest = s[end:].strip()
                m2 = re.match(DATE_RE.pattern, rest, re.IGNORECASE)  # optional value-date column
                if m2:
                    rest = rest[m2.end():].strip()
                desc, amounts = _split_amounts(rest)
                prev = _Entry(d, desc, amounts)
                entries.append(prev)
                continue
            mo = _OPENING.search(s)
            if mo:
                try:
                    opening = parse_amount(mo.group(1))
                except ValueError:
                    pass
            if _FOOTER.match(s):
                prev = None
                continue
            if prev is not None and not prev.closed:
                desc, amounts = _split_amounts(s)
                if amounts and not prev.amounts:
                    prev.amounts = amounts
                    prev.desc = (prev.desc + " " + desc).strip()
                elif not amounts and len(s) < 100:
                    prev.desc = (prev.desc + " " + s).strip()
                else:
                    prev.closed = True

    txns: List[Txn] = []
    prev_balance = opening
    uncertain = 0
    for i, e in enumerate(entries, start=1):
        if not e.amounts:
            errors.append({"row": i, "error": "No amount found on transaction line"})
            continue
        try:
            vals = [parse_amount(a) for a in e.amounts]
        except ValueError as exc:
            errors.append({"row": i, "error": str(exc)})
            continue
        suffix = [bool(re.search(r"(?i)\bdr\b", a)) for a in e.amounts], [bool(re.search(r"(?i)\bcr\b", a)) for a in e.amounts]
        balance: Optional[float] = None
        ttype: Optional[str] = None
        amount: Optional[float] = None
        n = len(vals)
        if n >= 3:
            a1, a2, balance = vals[-3], vals[-2], vals[-1]
            if hint.credit_first:
                a1, a2 = a2, a1  # now a1=debit, a2=credit
            if a1 and not a2:
                ttype, amount = "DEBIT", abs(a1)
            elif a2 and not a1:
                ttype, amount = "CREDIT", abs(a2)
            else:
                amount = abs(a1 or a2 or 0)
        elif n == 2 and hint.has_debit_credit and not hint.has_balance:
            a1, a2 = (vals[1], vals[0]) if hint.credit_first else (vals[0], vals[1])
            if a1 and not a2:
                ttype, amount = "DEBIT", abs(a1)
            elif a2 and not a1:
                ttype, amount = "CREDIT", abs(a2)
            else:
                amount = abs(a1 or a2 or 0)
        elif n >= 2:
            amount, balance = abs(vals[-2]), vals[-1]
            if suffix[0][-2]:
                ttype = "DEBIT"
            elif suffix[1][-2]:
                ttype = "CREDIT"
            elif vals[-2] < 0:
                ttype = "DEBIT"
        else:
            amount = abs(vals[0])
            ttype = "DEBIT" if (suffix[0][0] or vals[0] < 0) else ("CREDIT" if suffix[1][0] else None)
        if ttype is None and balance is not None and prev_balance is not None and amount is not None:
            delta = round(balance - prev_balance, 2)
            if abs(abs(delta) - amount) <= 0.02:
                ttype = "CREDIT" if delta > 0 else "DEBIT"
        if ttype is None:
            ttype = _guess_direction(e.desc)
            if ttype is None:
                ttype, uncertain = "DEBIT", uncertain + 1
        if balance is not None:
            prev_balance = balance
        if not amount:
            errors.append({"row": i, "error": "Zero or missing amount"})
            continue
        try:
            txns.append(build_transaction(
                source, e.date, e.desc, debit=amount if ttype == "DEBIT" else None,
                credit=amount if ttype == "CREDIT" else None, balance=balance,
                reference=_extract_reference(e.desc), row_number=i))
        except ValueError as exc:
            errors.append({"row": i, "error": str(exc)})
    if uncertain:
        warnings.append(f"Debit/credit direction could not be determined for {uncertain} row(s); defaulted to DEBIT.")
    return txns, errors, warnings


# ---------------------------------------------------------------- public API
def parse_pdf(content: bytes, source: str = BANK, bank: Optional[str] = None) -> ParseResult:
    if not content:
        from app.parsers.transaction_parser import EmptyFileError
        raise EmptyFileError("The uploaded file is empty.")
    if not content.lstrip()[:5] == b"%PDF-":
        raise MalformedFileError("File is not a valid PDF.")
    pages = _extract_pages_lines(content)
    full_text = "\n".join("\n".join(p) for p in pages)
    if len(re.sub(r"\s+", "", full_text)) < 30:
        raise ScannedPdfError(SCANNED_PDF_MESSAGE)

    for name, detector, parser in _BANK_PARSERS:
        if (bank and bank.lower() == name.lower()) or (not bank and detector(full_text)):
            res = parser(pages, source)
            res.file_type = "pdf"
            res.warnings.append(f"Parsed with bank-specific parser '{name}'.")
            return res

    t_txns, t_err = _parse_tables(_extract_tables(content), source)
    x_txns, x_err, x_warn = parse_text_lines(pages, source)
    if t_txns and len(t_txns) >= len(x_txns):
        txns, errors, warnings, method = t_txns, t_err, [], "table"
    else:
        txns, errors, warnings, method = x_txns, x_err, x_warn, "text"
    if not txns:
        raise NoTransactionsError("No transactions could be extracted from the PDF.")
    res = ParseResult(transactions=txns, skipped_rows=errors, warnings=warnings, file_type="pdf",
                      total_rows=len(txns) + len(errors))
    if errors:
        res.warnings.append(f"{len(errors)} row(s) skipped due to invalid data.")
    log.info("Parsed PDF pages=%d method=%s transactions=%d skipped=%d", len(pages), method, len(txns), len(errors))
    return res
