import datetime as dt

import pytest

from app.domain import CREDIT, DEBIT
from app.normalization.normalizer import build_transaction
from app.utils.amounts import format_money, parse_amount
from app.utils.dates import parse_date
from app.utils.text import normalize_description, normalize_reference, safe_filename, vendor_key


@pytest.mark.parametrize("raw,expected", [("₹5,000", 5000.0), ("5000", 5000.0), ("5,000.00", 5000.0), ("-5000", -5000.0),
                                          ("(5,000.00)", -5000.0), ("5000 Dr", -5000.0), ("Rs. 1,25,000.50", 125000.5),
                                          (7500, 7500.0), ("", None), ("-", None), (None, None)])
def test_parse_amount(raw, expected):
    assert parse_amount(raw) == expected


def test_parse_amount_invalid():
    with pytest.raises(ValueError):
        parse_amount("twelve")


@pytest.mark.parametrize("raw", ["2025-01-05", "05/01/2025", "05-01-2025", "5 Jan 2025", "05-Jan-2025", "Jan 5, 2025",
                                 "05.01.2025", "05/01/25"])
def test_parse_date_formats(raw):
    assert parse_date(raw) == dt.date(2025, 1, 5)


def test_parse_date_ambiguous_and_invalid():
    assert parse_date("04/13/2025") == dt.date(2025, 4, 13)  # impossible day-first falls back to month-first
    with pytest.raises(ValueError):
        parse_date("not a date")


def test_description_and_reference_normalisation():
    assert normalize_description("  NEFT--ABC   Suppliers, Pvt. Ltd.  ") == "neft abc suppliers pvt ltd"
    assert normalize_reference(" HDFC-N25/002 ") == "hdfcn25002"
    assert normalize_reference("N/A") is None
    assert vendor_key(normalize_description("NEFT-ABC SUPPLIERS PVT LTD-INV1001")) == "abc supplier"


def test_build_transaction_keeps_raw_and_types():
    t = build_transaction("BANK", "05/01/2025", "  UPI-Swiggy   Corporate ", debit="₹3,250.00", reference=" Ref-001 ")
    assert t.transaction_type == DEBIT and t.amount == 3250.0 and t.debit == 3250.0 and t.credit is None
    assert t.raw_description == "  UPI-Swiggy   Corporate " and t.normalized_description == "upi swiggy corporate"
    assert t.reference == "Ref-001" and t.normalized_reference == "ref001"
    c = build_transaction("ACCOUNTING", "2025-01-05", "x", amount="1,000")
    assert c.transaction_type == CREDIT
    assert build_transaction("ACCOUNTING", "2025-01-05", "x", amount="-1,000").transaction_type == DEBIT


def test_build_transaction_errors():
    for kwargs in ({"debit": "abc"}, {}, {"debit": "5", "credit": "5"}):
        with pytest.raises(ValueError):
            build_transaction("BANK", "2025-01-05", "x", **kwargs)
    with pytest.raises(ValueError):
        build_transaction("BANK", "garbage", "x", debit="5")


def test_helpers():
    assert format_money(125000.5) == "₹1,25,000.50"
    assert safe_filename("../../etc/pass wd.csv") == "pass_wd.csv"
