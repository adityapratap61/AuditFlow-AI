import pytest

from app.parsers.csv_parser import parse_csv
from app.parsers.transaction_parser import EmptyFileError, MalformedFileError, MissingColumnsError, NoTransactionsError


def test_sample_files_parse(sample_dir):
    bank = parse_csv((sample_dir / "bank_statement.csv").read_bytes(), "BANK")
    acct = parse_csv((sample_dir / "accounting_export.csv").read_bytes(), "ACCOUNTING")
    assert len(bank.transactions) == 34 and len(acct.transactions) == 32
    assert bank.columns["debit"] == "Debit" and acct.columns["vendor"] == "Vendor"
    assert not bank.skipped_rows and not acct.skipped_rows


def test_header_variations():
    csv = ("Txn Date,Narration,Withdrawal Amt.,Deposit Amt.,Closing Balance,UTR\n"
           "05-Jan-2025,NEFT-ABC,\"5,000.00\",,95000,UTR123456\n05/01/2025,SALARY,,\"20,000\",115000,\n")
    r = parse_csv(csv.encode(), "BANK")
    assert [t.transaction_type for t in r.transactions] == ["DEBIT", "CREDIT"]
    assert r.transactions[0].reference == "UTR123456" and r.transactions[0].balance == 95000.0


def test_single_amount_column_sign_and_type_hint():
    r = parse_csv(b"Date,Details,Amount\n2025-01-05,Pay vendor,-500\n2025-01-06,Receipt,700\n", "ACCOUNTING")
    assert [t.transaction_type for t in r.transactions] == ["DEBIT", "CREDIT"]
    r = parse_csv(b"Date,Description,Amount,Type\n2025-01-05,Pay vendor,500,DR\n", "ACCOUNTING")
    assert r.transactions[0].transaction_type == "DEBIT"


def test_semicolon_delimiter_and_preamble():
    csv = "Statement of account\nAccount: 123\nDate;Description;Debit;Credit\n05/01/2025;Fuel;100,00;\n"
    r = parse_csv(csv.replace("100,00", "100.00").encode(), "BANK")
    assert len(r.transactions) == 1 and r.transactions[0].amount == 100.0


def test_vendor_and_invoice_columns():
    r = parse_csv(b"Date,Vendor,Description,Amount,Invoice Number\n2025-01-05,ABC Supplier,Payment,-100,INV9001\n", "ACCOUNTING")
    t = r.transactions[0]
    assert t.vendor_key == "abc supplier" and "inv9001" in t.ref_keys and t.raw_description.startswith("ABC Supplier Payment")


def test_invalid_rows_are_skipped_not_fatal():
    r = parse_csv(b"Date,Description,Debit\n2025-01-05,ok,10\nbad-date,x,10\n2025-01-07,y,abc\n", "BANK")
    assert len(r.transactions) == 1 and len(r.skipped_rows) == 2 and r.warnings


def test_errors():
    with pytest.raises(EmptyFileError):
        parse_csv(b"   \n", "BANK")
    with pytest.raises(EmptyFileError):
        parse_csv(b"", "BANK")
    with pytest.raises(MissingColumnsError) as e:
        parse_csv(b"foo,bar\n1,2\n", "BANK")
    assert "date" in e.value.message
    with pytest.raises(MissingColumnsError):
        parse_csv(b"Date,Description\n2025-01-05,x\n", "BANK")
    with pytest.raises(MalformedFileError):
        parse_csv(b"%PDF-1.4 not csv", "BANK")
    with pytest.raises(NoTransactionsError):
        parse_csv(b"Date,Description,Debit\nnot-a-date,x,5\n", "BANK")
