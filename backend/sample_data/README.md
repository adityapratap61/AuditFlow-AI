# AuditFlow AI sample data
Regenerate with `python scripts/generate_sample_data.py` (deterministic).

Files: `bank_statement.csv` (34 txns), `bank_statement.pdf` (same statement as a text PDF), `accounting_export.csv` (32 txns, mixed date formats).

| Scenario | Where |
|---|---|
| Normal matches (reference / amount+date) | most rows |
| Vendor-name variations | "NEFT-ABC SUPPLIERS PVT LTD-INV1001" ↔ "ABC Supplier", "Patel & Sons" ↔ "Patel and Sons" |
| Timing differences | Kumar Transport (bank 08 Jan / books 10 Jan), ABC INV1022 (27 Jan / 29 Jan) |
| Amount mismatch | Verma Engineering: bank 76,500 vs books 74,500 |
| High-value mismatch | High Tension Cables: bank 4,50,000 vs books 3,00,000 |
| Duplicates | Zenith Logistics paid twice in bank; Mehta Packaging booked twice in accounting |
| Missing accounting entry | Tripathi Freight 31,000; bank charges 118 |
| Missing bank entry | Bose Interiors (unpresented cheque), Rao Stationers |
| Potentially suspicious (rule-based, needs manual verification) | "CASH WITHDRAWAL SELF" 1,20,000; QuickFix Traders 99,500 (just below threshold, unknown vendor) |
