# AuditFlow AI — API Documentation
**Reconcile. Investigate. Resolve.**

Base URL (dev): `http://127.0.0.1:8000` · Interactive docs: `/docs` · OpenAPI: `/openapi.json` · CORS: configurable (`CORS_ORIGINS`, default `*`). No authentication (hackathon MVP). All bodies are JSON except uploads (`multipart/form-data`). All IDs are 32-char hex strings. Dates are ISO `YYYY-MM-DD`; timestamps are UTC ISO-8601.

## Frontend flow
1. `POST /api/upload/bank` → returns `run_id`.
2. `POST /api/upload/accounting` with form field `run_id` → `ready_to_reconcile: true`.
3. `POST /api/reconcile {run_id}` (synchronous; returns summary + anomalies).
4. `GET /api/reconciliation/{run_id}` (status/summary any time), `GET /api/transactions?run_id=…`, `GET /api/matches?run_id=…`, `GET /api/anomalies?run_id=…&severity=HIGH`.
5. `POST /api/investigate/{anomaly_id}` to (re)run the agent; `GET /api/investigations/{id}` for the step trail.
6. `GET /api/report/{run_id}` (JSON) or `?format=csv`.

Run `status`: `created` (one file uploaded) → `ready` (both uploaded) → `processing` → `completed` | `failed`. Re-uploading a file into a run replaces that file's transactions and clears previous results.

## Enums
| Field | Values |
|---|---|
| `source` | `BANK`, `ACCOUNTING` |
| `transaction_type` | `DEBIT`, `CREDIT` |
| `match status` | `MATCHED` (≥90), `LIKELY_MATCH` (75–89), `REVIEW_REQUIRED` (50–74), `UNMATCHED` (<50) — thresholds configurable |
| `anomaly_type` | `MISSING_TRANSACTION`, `DUPLICATE_TRANSACTION`, `TIMING_DIFFERENCE`, `AMOUNT_MISMATCH`, `HIGH_VALUE_MISMATCH`, `POTENTIALLY_SUSPICIOUS` |
| `severity` | `HIGH`, `MEDIUM`, `LOW` |
| anomaly `status` | `OPEN`, `INVESTIGATED` |
| `overall_status` | `RECONCILED`, `REVIEW_NEEDED`, `ATTENTION_REQUIRED` |
| `explanation_source` | `ollama` (validated LLM text) or `fallback` (deterministic) |
| match `level` | 1 reference · 2 amount+date · 3 amount+fuzzy description · 4 fuzzy description+close amount/date · 5 agent relaxed-tolerance retry |

`POTENTIALLY_SUSPICIOUS` is a conservative rule-based indicator: *"Potentially suspicious transaction requiring manual verification."* The system never states that fraud is confirmed.

## Errors
Every error has the shape `{"error": {"code": "...", "message": "...", "details": [...optional]}}`. No stack traces or filesystem paths are ever returned.

| HTTP | code | When |
|---|---|---|
| 400 | `EMPTY_FILE` | empty upload |
| 404 | `RUN_NOT_FOUND`, `TRANSACTION_NOT_FOUND`, `ANOMALY_NOT_FOUND`, `INVESTIGATION_NOT_FOUND`, `NOT_FOUND` | unknown id/route |
| 409 | `RUN_NOT_READY` | reconcile before both files uploaded |
| 409 | `RUN_BUSY` | run is processing |
| 409 | `RUN_NOT_COMPLETED` | report requested before completion |
| 413 | `FILE_TOO_LARGE` | above `MAX_UPLOAD_MB` (default 20) |
| 415 | `UNSUPPORTED_FILE_TYPE` | bank: `.csv`/`.pdf`; accounting: `.csv` |
| 422 | `MALFORMED_FILE`, `MISSING_COLUMNS`, `NO_TRANSACTIONS`, `VALIDATION_ERROR` | bad content / params |
| 422 | `SCANNED_PDF` | message: *Scanned/image-only PDF detected. OCR is not enabled in Phase 1.* |
| 500 | `RECONCILIATION_FAILED`, `DATABASE_ERROR`, `INTERNAL_ERROR` | server-side failure |

Pagination: list endpoints take `limit` (1–500, default 50) and `offset`, and return `{"items": [...], "total": n, "limit": n, "offset": n}`.

---
## GET /health
Liveness. Healthy even when Ollama is down (HTTP 503 + `"unhealthy"` only if the database is unreachable).
```json
{"status":"healthy","database":"connected","ollama":"unavailable","service":"AuditFlow AI","tagline":"Reconcile. Investigate. Resolve.","version":"1.0.0"}
```

## POST /api/upload/bank
Upload a bank statement (`.csv` or text-based `.pdf`). Form fields: `file` (required), `run_id` (optional – omit to start a new run).
```bash
curl -F "file=@sample_data/bank_statement.csv" http://127.0.0.1:8000/api/upload/bank
```
```json
{"run_id":"3f2c…","source":"BANK","filename":"bank_statement.csv","file_type":"csv","transactions_extracted":34,
 "skipped_rows":0,"parse_errors":[],"warnings":[],"run_status":"created","bank_uploaded":true,
 "accounting_uploaded":false,"ready_to_reconcile":false}
```
`parse_errors` = `[{"row": 12, "error": "Invalid date: 'xx'"}]` (first 50). Errors: 400/413/415/422/404 (unknown `run_id`).

## POST /api/upload/accounting
Same as above, `.csv` only, with the existing `run_id`. Recognised columns include Date, Vendor/Party, Description/Narration, Amount/Debit/Credit, Reference/UTR/Transaction ID, Invoice Number, Balance, Currency, Type (Dr/Cr).
```bash
curl -F "file=@sample_data/accounting_export.csv" -F "run_id=3f2c…" http://127.0.0.1:8000/api/upload/accounting
```

## POST /api/reconcile
Runs parsing results → matching → anomaly detection → investigation agent → explanations → report data. Synchronous.
Request: `{"run_id": "3f2c…", "use_llm": true}` (`use_llm` optional; Ollama is used only if available).
```json
{"run_id":"3f2c…","status":"completed","overall_status":"ATTENTION_REQUIRED","processing_time":0.42,
 "summary":{"total_bank_transactions":34,"total_accounting_transactions":32,"matched":26,"likely_matches":1,
   "review_required":2,"unmatched":5,"unmatched_accounting":2,"match_rate":0.7941,"total_anomalies":16,"high_risk":5,
   "anomaly_counts":{"MISSING_TRANSACTION":6,"DUPLICATE_TRANSACTION":2,"TIMING_DIFFERENCE":2,"AMOUNT_MISMATCH":2,
   "HIGH_VALUE_MISMATCH":2,"POTENTIALLY_SUSPICIOUS":2},"high_value_mismatches":2,"suspicious_transactions":2,
   "duplicate_groups":2,"duplicate_group_details":[{"id":"…","source":"BANK","transaction_ids":["…","…"],"confidence":0.9,"explanation":"…"}]},
 "narrative":"AuditFlow AI reconciled 34 bank and 32 accounting transactions: …",
 "anomalies":[{"id":"…","run_id":"…","transaction_id":"…","related_transaction_id":"…","anomaly_type":"AMOUNT_MISMATCH",
   "initial_type":"MISSING_TRANSACTION","severity":"HIGH","status":"INVESTIGATED","source":"BANK","confidence":0.88,
   "description":"Likely the same transaction with different amounts: …","details":{"amount_difference":150000.0},
   "explanation":"The bank transaction of ₹4,50,000.00 …","explanation_source":"fallback","investigation_id":"…","created_at":"…"}],
 "bank_filename":"bank_statement.csv","accounting_filename":"accounting_export.csv","created_at":"…","completed_at":"…","error":null}
```
(Figures above are illustrative; exact counts come from your data.) Anomalies are sorted HIGH → LOW. Errors: 404, 409 (`RUN_NOT_READY`, `RUN_BUSY`), 500 `RECONCILIATION_FAILED` (run marked `failed`).

## GET /api/reconciliation/{run_id}
Same schema as above; `summary`/`anomalies` are null/empty until `status` is `completed`. Poll `status` if you reconcile from another client.

## GET /api/reconciliations
List runs (newest first, without anomaly arrays). Query: `limit`, `offset`. Returns `{items:[ReconciliationResponse], total, limit, offset}`.

## GET /api/transactions
Query: `run_id`, `source`, `match_status`, `transaction_type`, `date_from`, `date_to`, `min_amount`, `max_amount`, `search` (description/reference substring), `limit`, `offset`. Ordered by date.
```json
{"items":[{"id":"…","run_id":"…","source":"BANK","date":"2025-01-02","description":"NEFT-ABC SUPPLIERS PVT LTD-INV1001",
 "amount":45000.0,"transaction_type":"DEBIT","debit":45000.0,"credit":null,"reference":"HDFCN25002123401","balance":955000.0,
 "currency":"INR","raw_description":"NEFT-ABC SUPPLIERS PVT LTD-INV1001","normalized_description":"neft abc suppliers pvt ltd inv1001",
 "row_number":2,"match_status":"MATCHED","matched_transaction_id":"…"}],"total":34,"limit":50,"offset":0}
```
`amount` is always positive; direction is `transaction_type`. `raw_description` is never altered.

## GET /api/transactions/{transaction_id}
Transaction fields plus `match` (full match object) and `anomalies` (list of anomalies on/related to it). 404 `TRANSACTION_NOT_FOUND`.

## GET /api/matches
Query: `run_id`, `status`, `matched_by` (`ENGINE`|`AGENT`), `min_score`, `max_score`, `limit`, `offset`. Ordered by score desc. One row per bank transaction.
```json
{"items":[{"id":"…","run_id":"…","bank_transaction_id":"…","accounting_transaction_id":"…","score":100.0,"status":"MATCHED","level":1,
 "signals":{"amount_score":40.0,"date_score":20.0,"description_score":20.0,"reference_score":20.0},
 "reasons":["amount is identical","same date","description similarity 100%","reference numbers are identical"],
 "date_diff_days":0,"description_similarity":100.0,"amount_difference":0.0,"matched_by":"ENGINE",
 "bank_transaction":{…},"accounting_transaction":{…}}],"total":26,"limit":50,"offset":0}
```
`accounting_transaction_id` is null for `UNMATCHED`. Signals are points earned per signal (weights configurable); inapplicable signals (e.g. no reference on either side) are excluded and the total is rescaled to 100.

## GET /api/anomalies
Query: `run_id`, `anomaly_type`, `severity`, `status`, `source`, `limit`, `offset`. Sorted by severity. Item schema = anomaly object in the reconcile response.

## GET /api/anomalies/{anomaly_id}
Anomaly plus `transaction` and `related_transaction` (full transaction objects or null). 404 `ANOMALY_NOT_FOUND`.

## POST /api/investigate/{anomaly_id}
Runs the investigation agent for the anomaly's transaction now and stores a new investigation (anomalies of that transaction become `INVESTIGATED`). Body optional: `{"use_llm": true}`.
The agent's tools: `search_by_amount`, `search_by_reference`, `search_by_date_range`, `retry_with_relaxed_tolerance`, `search_by_description`, `fuzzy_search_transactions`, `compare_transactions`, `check_duplicates` — each next step depends on the previous result and the decision is stored.
```json
{"id":"…","run_id":"…","anomaly_id":"…","transaction_id":"…","status":"completed","conclusion":"TIMING_DIFFERENCE","confidence":0.93,
 "explanation":"The bank transaction of ₹22,500.00 dated 2025-01-08 has no accounting match within the strict date tolerance. … Manual verification is recommended.",
 "explanation_source":"fallback","explanation_detail":{"evidence_points":["…"],"inference":"…","recommended_action":"…"},
 "evidence":{"transaction":{…},"counterpart":{…},"comparison":{"date_difference_days":2,"description_similarity":100.0,…}},
 "counterpart_transaction_id":"…","created_at":"…","completed_at":"…",
 "steps":[{"id":"…","step_number":1,"tool":"search_by_amount","arguments":{"amount":22500.0},
   "result_summary":"1 available candidate(s) with identical amount","candidate_ids":["…"],
   "decision":"1 same-amount candidate(s); narrowing by reference and date","created_at":"…"}]}
```
`conclusion` is the agent's own finding and may differ from the anomaly's original `anomaly_type`. Errors: 404 `ANOMALY_NOT_FOUND`.

## GET /api/investigations/{investigation_id}
Same schema. Investigations are also created automatically for every anomaly during `/api/reconcile` (see `investigation_id` on each anomaly). 404 `INVESTIGATION_NOT_FOUND`.

## GET /api/investigations
Query: `run_id`, `anomaly_id`, `limit`, `offset`. Returns an array of investigations.

## GET /api/report/{run_id}
Query: `format=json` (default) or `format=csv` (anomaly export, `text/csv` download). Requires a completed run (409 otherwise).
JSON keys: `report_metadata` (product, tagline, version, generated_at, run_id, files), `overall_status`, `totals`, `summary`, `narrative`, `anomaly_counts`, `severity_counts`, `high_value_mismatches[]`, `suspicious_transactions[]` (each with `disclaimer`), `duplicate_groups[]`, `investigation_summaries[]`, `disclaimer`. Generating the JSON report also stores it in the `reports` table.
