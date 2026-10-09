# AuditFlow AI — Backend (Phase 1)
**Reconcile. Investigate. Resolve.**

AI-powered bank statement reconciliation & anomaly investigation agent. Phase 1 = REST backend + reconciliation engine + agentic investigation. The Phase 2 frontend (Next.js/React) will consume the API documented in [`backend/API_DOCUMENTATION.md`](backend/API_DOCUMENTATION.md).

## Problem → solution
Bank statements and accounting exports disagree (timing, naming, missing/duplicate entries, bank charges, amount differences). AuditFlow AI parses both, matches them with a multi-signal scoring engine, flags anomalies with deterministic rules, then runs a tool-using investigation agent on every unresolved item and explains findings (local Ollama LLM, with a deterministic fallback so it works fully offline).

## Architecture
```
bank CSV/PDF + accounting CSV → parsers → normalisation → candidate-indexed matcher (levels 1-4) + scoring
  → anomaly rules (missing, duplicate, timing, amount, high-value, suspicious)
  → investigation agent (8 tools, adaptive steps, relaxed-tolerance retry = level 5, trail stored)
  → explanation (Ollama JSON, validated against evidence, else deterministic fallback) → SQLite → REST API → report
```
`app/parsers` file → transactions (pluggable bank-specific PDF parsers via `register_bank_parser`) · `app/matching` index, fuzzy (RapidFuzz), scoring, tolerances · `app/anomaly` rules/detector · `app/agent` tools/investigation/orchestration · `app/llm` Ollama client, prompts, validation, fallback · `app/services` DB-facing logic · `app/api` routes · `app/core/config.py` all settings.

The LLM only *phrases* explanations/summaries from structured evidence. Amounts, dates, matching and anomaly detection are plain Python. LLM output is rejected (→ fallback) if malformed, if it contains numbers absent from the evidence, or if it asserts fraud.

## Features
CSV (flexible headers/delimiters) and text-PDF bank statements (table + line parsers; scanned PDFs → clear error, no OCR) · configurable weights (40/20/20/20), thresholds (90/75/50), date tolerance (±1 strict, ±3 relaxed), high-value threshold · one-to-one matching with candidate filtering (5,000×5,000 in seconds) · duplicate groups with confidence · full investigation trail per anomaly · JSON/CSV reports · consistent JSON errors.

## Install & run
```bash
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt                        # Python 3.11+
cp .env.example .env                                   # optional; defaults work
python run.py                                          # http://127.0.0.1:8000  (docs at /docs)
```
Env vars (see `.env.example`): `DATABASE_URL`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `HIGH_VALUE_THRESHOLD`, `STRICT_/RELAXED_DATE_TOLERANCE_DAYS`, `MATCH_/LIKELY_MATCH_/REVIEW_THRESHOLD`, `*_SCORE_WEIGHT`, plus `MAX_UPLOAD_MB`, `CORS_ORIGINS`, `LOG_LEVEL`, `LLM_MAX_EXPLANATIONS`, `HOST`, `PORT`.

## Ollama (optional)
```bash
ollama serve &
ollama pull llama3.1:8b          # any local model works; qwen2.5:7b, mistral, etc.
echo "OLLAMA_MODEL=llama3.1:8b" >> .env
```
Leave `OLLAMA_MODEL` empty to auto-use the first installed model. `GET /health` shows `"ollama": "available|unavailable"`. Without Ollama everything works using deterministic explanations (`explanation_source: "fallback"`). At most `LLM_MAX_EXPLANATIONS` (25) anomalies per run use the LLM to bound latency.

## Try it
```bash
curl -F "file=@sample_data/bank_statement.csv" localhost:8000/api/upload/bank          # → run_id
curl -F "file=@sample_data/accounting_export.csv" -F "run_id=<run_id>" localhost:8000/api/upload/accounting
curl -X POST localhost:8000/api/reconcile -H 'content-type: application/json' -d '{"run_id":"<run_id>"}'
curl localhost:8000/api/report/<run_id>
```
Sample data (34 bank / 32 accounting rows covering every scenario, plus a PDF version) lives in `sample_data/` — see its README.

## Tests
```bash
cd backend && pytest -q
```
No Ollama needed (it is mocked / confirmed unreachable). Covers parsing, normalisation, matching, tolerances, scoring, every anomaly type, the agent trail, LLM fallback/validation and the REST API.

## Limitations
Scanned PDFs are not supported (no OCR). PDF layouts are handled generically; unusual banks may need a plugin via `register_bank_parser`. Debit/credit direction is not used as a matching signal (sign conventions differ between exports). Single-currency assumption (INR default; currency column is stored). Reconciliation runs synchronously inside the request. No authentication. SQLite only (SQLAlchemy URL is swappable).

## Future improvements
OCR for scanned statements, bank-specific parsers, background jobs/progress, auth & multi-tenant, many-to-one (split/batched payments) matching, learning from user resolutions, PDF reports, the Phase 2 frontend.

## Phase 2 — Frontend
See [`frontend/README.md`](frontend/README.md). Quick start: run the backend (`cd backend && python run.py`), then `cd frontend && cp .env.example .env.local && npm install && npm run dev`.
