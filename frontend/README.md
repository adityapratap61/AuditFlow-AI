# AuditFlow AI — Frontend
**Reconcile. Investigate. Resolve.** — Next.js 14 · React 18 · TypeScript · Tailwind · Recharts · Lucide.

## Requirements
- Node.js 18.17+ (20 LTS recommended), npm
- The Phase 1 backend running (default `http://localhost:8000`)

## Setup
```bash
cd frontend
cp .env.example .env.local      # NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev                     # http://localhost:3000
```
Backend (separate terminal): `cd backend && pip install -r requirements.txt && python run.py`

The backend allows all origins by default (`CORS_ORIGINS=*`). If you restrict it, add `http://localhost:3000`.

## Scripts
`npm run dev` · `npm run build` · `npm start` · `npm run typecheck`

## How it connects
All HTTP calls live in `lib/api.ts` (typed, uses `NEXT_PUBLIC_API_URL`). The active `run_id` is kept in `localStorage` (falls back to the latest completed run). No mock data: every number, chart, table, investigation step and report comes from the backend.

Flow: upload bank → upload accounting → `POST /api/reconcile` → dashboard / transactions / anomalies → `POST /api/investigate/{id}` → report (`/api/report/{run}`, JSON/CSV download).

**Load Sample Data** (or *View Demo* on the home page) loads `public/sample/*` (copies of `backend/sample_data`) into the upload form; they are then processed by the real backend. If you change the backend samples, re-copy them.

## Production notes
`NEXT_PUBLIC_*` variables are inlined at build time — set `NEXT_PUBLIC_API_URL` before `npm run build`. Never put secrets in frontend env vars. Reconciliation is a synchronous backend call, so large files show a loading state until it returns.
