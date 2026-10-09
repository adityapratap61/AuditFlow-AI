import { API_URL } from "./constants";
import type {
  Anomaly, AnomalyDetail, APIErrorBody, Health, Investigation, Match, Page, ReconciliationResult, Report,
  Transaction, TransactionDetail, UploadResult,
} from "./types";

export class ApiError extends Error {
  code: string; status: number; details?: unknown[];
  constructor(status: number, code: string, message: string, details?: unknown[]) {
    super(message); this.name = "ApiError"; this.status = status; this.code = code; this.details = details;
  }
  get isNetwork(): boolean { return this.code === "NETWORK_ERROR"; }
}

const NETWORK_MSG = "Unable to connect to AuditFlow AI backend. Please make sure the backend is running.";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try { res = await fetch(`${API_URL}${path}`, { cache: "no-store", ...init }); }
  catch { throw new ApiError(0, "NETWORK_ERROR", NETWORK_MSG); }
  if (!res.ok) throw await toError(res);
  return (await res.json()) as T;
}
async function toError(res: Response): Promise<ApiError> {
  try {
    const body = (await res.json()) as { error?: APIErrorBody };
    if (body?.error) return new ApiError(res.status, body.error.code, body.error.message, body.error.details);
  } catch { /* non-JSON body */ }
  return new ApiError(res.status, "HTTP_ERROR", "The server returned an unexpected response.");
}
function qs(params: Record<string, string | number | undefined | null>): string {
  const u = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") u.set(k, String(v));
  const s = u.toString();
  return s ? `?${s}` : "";
}

export const api = {
  health: () => request<Health>("/health"),

  uploadBank: (file: File, runId?: string) => upload("/api/upload/bank", file, runId),
  uploadAccounting: (file: File, runId?: string) => upload("/api/upload/accounting", file, runId),

  reconcile: (runId: string, useLlm = true) =>
    request<ReconciliationResult>("/api/reconcile", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ run_id: runId, use_llm: useLlm }),
    }),
  getRun: (runId: string) => request<ReconciliationResult>(`/api/reconciliation/${runId}`),
  listRuns: (limit = 20, offset = 0) =>
    request<Page<ReconciliationResult>>(`/api/reconciliations${qs({ limit, offset })}`),

  transactions: (p: { run_id: string; source?: string; match_status?: string; search?: string; limit?: number; offset?: number }) =>
    request<Page<Transaction>>(`/api/transactions${qs(p)}`),
  transaction: (id: string) => request<TransactionDetail>(`/api/transactions/${id}`),
  matches: (p: { run_id: string; status?: string; limit?: number; offset?: number }) =>
    request<Page<Match>>(`/api/matches${qs(p)}`),

  anomalies: (p: { run_id: string; anomaly_type?: string; severity?: string; limit?: number; offset?: number }) =>
    request<Page<Anomaly>>(`/api/anomalies${qs(p)}`),
  anomaly: (id: string) => request<AnomalyDetail>(`/api/anomalies/${id}`),

  investigate: (anomalyId: string, useLlm = true) =>
    request<Investigation>(`/api/investigate/${anomalyId}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ use_llm: useLlm }),
    }),
  investigation: (id: string) => request<Investigation>(`/api/investigations/${id}`),
  investigations: (p: { run_id?: string; anomaly_id?: string; limit?: number; offset?: number }) =>
    request<Investigation[]>(`/api/investigations${qs(p)}`),

  report: (runId: string) => request<Report>(`/api/report/${runId}`),
  async reportBlob(runId: string, format: "json" | "csv"): Promise<Blob> {
    let res: Response;
    try { res = await fetch(`${API_URL}/api/report/${runId}${qs({ format })}`, { cache: "no-store" }); }
    catch { throw new ApiError(0, "NETWORK_ERROR", NETWORK_MSG); }
    if (!res.ok) throw await toError(res);
    return res.blob();
  },
};

async function upload(path: string, file: File, runId?: string): Promise<UploadResult> {
  const fd = new FormData();
  fd.append("file", file);
  if (runId) fd.append("run_id", runId);
  return request<UploadResult>(path, { method: "POST", body: fd });
}

/** Fetch every page of a list endpoint (500 per request). */
export async function fetchAll<T>(page: (limit: number, offset: number) => Promise<Page<T>>, max = 5000): Promise<T[]> {
  const out: T[] = [];
  let offset = 0;
  for (;;) {
    const p = await page(500, offset);
    out.push(...p.items);
    offset += p.items.length;
    if (p.items.length === 0 || offset >= p.total || offset >= max) break;
  }
  return out;
}

export function errorMessage(e: unknown, fallback: string): string {
  if (e instanceof ApiError) return e.isNetwork ? e.message : e.message || fallback;
  return fallback;
}
