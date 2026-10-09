import pytest

from app.parsers.csv_parser import parse_csv
from app.parsers.pdf_parser import parse_pdf, parse_text_lines
from app.parsers.transaction_parser import (SCANNED_PDF_MESSAGE, EmptyFileError, MalformedFileError, NoTransactionsError,
                                            ScannedPdfError)
from app.utils.simple_pdf import build_text_pdf


def test_sample_pdf_matches_csv(sample_dir):
    pdf = parse_pdf((sample_dir / "bank_statement.pdf").read_bytes())
    csv = parse_csv((sample_dir / "bank_statement.csv").read_bytes(), "BANK")
    assert len(pdf.transactions) == len(csv.transactions) == 34 and pdf.file_type == "pdf"
    for p, c in zip(pdf.transactions, csv.transactions):
        assert (p.date, p.amount, p.transaction_type) == (c.date, c.amount, c.transaction_type)
    assert any(t.reference == "HDFCN25002123401" for t in pdf.transactions)


def test_text_lines_variants_and_continuations():
    lines = [["Date Narration Withdrawal Deposit Balance", "Opening Balance 10,000.00",
              "05/01/2025 NEFT-ABC SUPPLIERS 2,000.00 8,000.00",
              "06-Jan-2025 SALARY CREDIT FOR JANUARY",
              "ACME CORP 5,000.00 13,000.00",
              "07 Jan 2025 ATM WDL 1,000.00 Dr 12,000.00", "Page 1 of 1"]]
    txns, errors, _ = parse_text_lines(lines)
    assert [(t.amount, t.transaction_type) for t in txns] == [(2000.0, "DEBIT"), (5000.0, "CREDIT"), (1000.0, "DEBIT")]
    assert "acme corp" in txns[1].normalized_description and not errors


def test_debit_credit_columns_without_balance():
    lines = [["Date Description Debit Credit", "05/01/2025 Rent 1,500.00 0.00", "06/01/2025 Refund 0.00 300.00"]]
    txns, _, _ = parse_text_lines(lines)
    assert [(t.amount, t.transaction_type) for t in txns] == [(1500.0, "DEBIT"), (300.0, "CREDIT")]


def test_scanned_pdf_message():
    with pytest.raises(ScannedPdfError) as e:
        parse_pdf(build_text_pdf([]))
    assert e.value.message == SCANNED_PDF_MESSAGE == "Scanned/image-only PDF detected. OCR is not enabled in Phase 1."


def test_no_transactions_and_bad_files():
    text = ["This document has plenty of readable text but it contains no transaction rows at all."]
    with pytest.raises(NoTransactionsError):
        parse_pdf(build_text_pdf(text))
    with pytest.raises(MalformedFileError):
        parse_pdf(b"definitely not a pdf")
    with pytest.raises(MalformedFileError):
        parse_pdf(b"%PDF-1.4\ngarbage garbage garbage")
    with pytest.raises(EmptyFileError):
        parse_pdf(b"")
