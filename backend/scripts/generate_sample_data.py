"""Generate AuditFlow AI sample data: bank_statement.csv/.pdf and accounting_export.csv.

Usage: python scripts/generate_sample_data.py   (run from backend/)
Deterministic; demonstrates matches, vendor-name variations, timing/amount/high-value mismatches,
missing entries, duplicates (bank + accounting side) and potentially suspicious transactions.
"""
import csv
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.utils.simple_pdf import build_text_pdf  # noqa: E402

OPENING = 1_000_000.00
D, C = "D", "C"
# (date, bank narration, type, amount, UTR/reference)
BANK = [
    ("2025-01-02", "NEFT-ABC SUPPLIERS PVT LTD-INV1001", D, 45000, "HDFCN25002123401"),
    ("2025-01-02", "UPI-SWIGGY CORPORATE", D, 3250, ""),
    ("2025-01-03", "RTGS-GLOBAL TECH SOLUTIONS LTD", D, 150000, "HDFCR25003998812"),
    ("2025-01-03", "NEFT CR-XYZ CLIENT LLP", C, 275000, "SBINN25003112233"),
    ("2025-01-04", "IMPS-OFFICE MART STATIONERY", D, 8420, ""),
    ("2025-01-05", "UPI-ZOMATO", D, 2100, ""),
    ("2025-01-06", "NEFT-RELIANCE POWER BILL", D, 18760, ""),
    ("2025-01-07", "BANK CHARGES-SMS ALERT QTR", D, 118, ""),
    ("2025-01-08", "NEFT-KUMAR TRANSPORT", D, 22500, ""),
    ("2025-01-09", "NEFT-LAKSHMI TEXTILES", D, 64000, ""),
    ("2025-01-10", "UPI-AMAZON BUSINESS", D, 12999, ""),
    ("2025-01-11", "CHQ DEP-PATEL & SONS", C, 98000, ""),
    ("2025-01-12", "NEFT-DELTA PRINTING", D, 15750, ""),
    ("2025-01-13", "NEFT-SHARMA CONSULTANTS", D, 35000, ""),
    ("2025-01-14", "NEFT-ZENITH LOGISTICS", D, 52000, "AXISN25014000111"),
    ("2025-01-14", "NEFT-ZENITH LOGISTICS", D, 52000, "AXISN25014000222"),
    ("2025-01-15", "NEFT-VERMA ENGINEERING WORKS", D, 76500, ""),
    ("2025-01-16", "NEFT-HIGH TENSION CABLES IND", D, 450000, "ICICN25016777001"),
    ("2025-01-17", "CASH WITHDRAWAL SELF CHQ 000451", D, 120000, ""),
    ("2025-01-18", "NEFT-MEHTA PACKAGING", D, 28300, ""),
    ("2025-01-19", "NEFT-ROYAL CATERERS", D, 26400, ""),
    ("2025-01-20", "UPI-GOOGLE WORKSPACE", D, 4720, ""),
    ("2025-01-21", "NEFT-ORION SOFTWARE LICENSES", D, 95000, ""),
    ("2025-01-22", "NEFT CR-SINGH & CO ADVISORS", C, 56000, ""),
    ("2025-01-23", "NEFT-TRIPATHI FREIGHT", D, 31000, ""),
    ("2025-01-24", "EMI-HDFC LOAN 4411", D, 42000, ""),
    ("2025-01-25", "NEFT CR-ARORA RETAIL", C, 310000, ""),
    ("2025-01-26", "NEFT-KAPOOR HARDWARE", D, 11800, ""),
    ("2025-01-27", "NEFT-ABC SUPPLIERS PVT LTD-INV1022", D, 38500, "HDFCN25027555123"),
    ("2025-01-28", "NEFT-NATIONAL INSURANCE CO", D, 22000, ""),
    ("2025-01-29", "UPI-UBER INDIA", D, 1850, ""),
    ("2025-01-30", "NEFT-IYER ASSOCIATES", D, 67000, ""),
    ("2025-01-31", "INTEREST CREDIT", C, 2140.50, ""),
    ("2025-01-31", "NEFT-QUICKFIX TRADERS", D, 99500, ""),
]
# (date, vendor, description, type, amount, invoice, reference)
ACCT = [
    ("2025-01-02", "ABC Supplier", "Payment for INV1001", D, 45000, "INV1001", "HDFCN25002123401"),
    ("2025-01-02", "Swiggy", "Team lunch", D, 3250, "", ""),
    ("2025-01-03", "Global Tech Solutions Ltd", "Server hardware", D, 150000, "", "HDFCR25003998812"),
    ("2025-01-03", "XYZ Client LLP", "Receipt against invoice 2024-118", C, 275000, "", "SBINN25003112233"),
    ("2025-01-04", "Office Mart Stationery", "Stationery purchase", D, 8420, "", ""),
    ("2025-01-06", "Zomato", "Staff meals", D, 2100, "", ""),
    ("2025-01-06", "Reliance Power", "Electricity - January", D, 18760, "", ""),
    ("2025-01-10", "Kumar Transport", "Freight charges", D, 22500, "", ""),
    ("2025-01-09", "Lakshmi Textiles", "Fabric purchase", D, 64000, "", ""),
    ("2025-01-10", "Amazon Business", "Office supplies", D, 12999, "", ""),
    ("2025-01-11", "Patel and Sons", "Customer receipt", C, 98000, "", ""),
    ("2025-01-13", "Delta Printing Press", "Printing job", D, 15750, "", ""),
    ("2025-01-13", "Sharma Consultancy", "Consulting fees", D, 35000, "", ""),
    ("2025-01-14", "Zenith Logistics", "Logistics services", D, 52000, "", "AXISN25014000111"),
    ("2025-01-15", "Verma Engineering Works", "Invoice INV1015", D, 74500, "INV1015", ""),
    ("2025-01-16", "High Tension Cables Industries", "Cable supply", D, 300000, "", "ICICN25016777001"),
    ("2025-01-18", "Mehta Packaging", "Packaging material", D, 28300, "", ""),
    ("2025-01-18", "Mehta Packaging", "Packaging material", D, 28300, "", ""),
    ("2025-01-19", "Royal Caterers", "Event catering", D, 26400, "", ""),
    ("2025-01-20", "Google Workspace", "Subscription", D, 4720, "", ""),
    ("2025-01-21", "Orion Software Licenses", "Annual licences", D, 95000, "", ""),
    ("2025-01-22", "Singh and Co Advisors", "Advisory receipt", C, 56000, "", ""),
    ("2025-01-24", "HDFC Loan EMI", "Loan instalment", D, 42000, "", ""),
    ("2025-01-25", "Arora Retail", "Customer receipt", C, 310000, "", ""),
    ("2025-01-26", "Kapoor Hardware", "Hardware purchase", D, 11800, "", ""),
    ("2025-01-29", "ABC Supplier", "Payment for INV1022", D, 38500, "INV1022", "HDFCN25027555123"),
    ("2025-01-28", "National Insurance Company", "Premium", D, 22000, "", ""),
    ("2025-01-29", "Uber India", "Local travel", D, 1850, "", ""),
    ("2025-01-30", "Iyer Associates", "Professional fees", D, 67000, "", ""),
    ("2025-01-31", "Bank Interest", "Savings interest", C, 2140.50, "", ""),
    ("2025-01-31", "Bose Interiors", "Cheque issued - not yet presented", D, 17500, "", ""),
    ("2025-01-30", "Rao Stationers", "Petty purchase", D, 5400, "", ""),
]


def money(x):
    return f"{x:,.2f}"


def main():
    out = ROOT / "sample_data"
    out.mkdir(exist_ok=True)
    bal = OPENING
    rows, lines = [], [
        "AUDITFLOW DEMO BANK - Statement of Account", "Account No: XXXXXX4411   Period: 01/01/2025 to 31/01/2025", "",
        "Date        Narration                                         Debit        Credit         Balance",
        f"Opening Balance {money(OPENING)}"]
    for d, desc, t, amt, ref in BANK:
        bal += amt if t == C else -amt
        dd = datetime.strptime(d, "%Y-%m-%d").strftime("%d/%m/%Y")
        rows.append([dd, desc, money(amt) if t == D else "", money(amt) if t == C else "", money(bal), ref])
        narr = f"{desc} {('UTR ' + ref) if ref else ''}".strip()
        lines.append(f"{dd} {narr[:62]:<62} {money(amt):>12} {money(bal):>14}")
    lines.append("")
    lines.append("Closing Balance " + money(bal))
    with open(out / "bank_statement.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Date", "Description", "Debit", "Credit", "Balance", "Reference"])
        w.writerows(rows)
    (out / "bank_statement.pdf").write_bytes(build_text_pdf(lines))
    with open(out / "accounting_export.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Date", "Vendor", "Description", "Debit", "Credit", "Invoice Number", "Reference"])
        for i, (d, v, desc, t, amt, inv, ref) in enumerate(ACCT):
            dt = datetime.strptime(d, "%Y-%m-%d")
            ds = dt.strftime("%d-%b-%Y") if i % 4 == 3 else d
            w.writerow([ds, v, desc, money(amt) if t == D else "", money(amt) if t == C else "", inv, ref])
    print(f"bank={len(BANK)} accounting={len(ACCT)} -> {out}")


if __name__ == "__main__":
    main()
