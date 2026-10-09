import type { Severity, Transaction, MatchStatus, Anomaly } from "./types";

export function cn(...c: (string | false | null | undefined)[]): string { return c.filter(Boolean).join(" "); }

const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 });
export function formatMoney(v: number | null | undefined, currency = "INR"): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  if (currency === "INR") return inr.format(v);
  try { return new Intl.NumberFormat("en-IN", { style: "currency", currency }).format(v); } catch { return `${currency} ${v}`; }
}
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00` : iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("en-GB", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}
export function pct(v: number | null | undefined, isFraction = true): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${Math.round(isFraction ? v * 100 : v)}%`;
}
export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1048576) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1048576).toFixed(1)} MB`;
}
export function fileExt(name: string): string { const i = name.lastIndexOf("."); return i < 0 ? "" : name.slice(i).toLowerCase(); }
export function humanize(s: string): string {
  return s.replace(/_/g, " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
}
export function toInt(v: unknown): number { return typeof v === "number" && Number.isFinite(v) ? v : 0; }

const RANK: Record<Severity, number> = { HIGH: 3, MEDIUM: 2, LOW: 1 };
export function maxSeverity(list: Anomaly[]): Severity | null {
  let best: Severity | null = null;
  for (const a of list) if (!best || RANK[a.severity] > RANK[best]) best = a.severity;
  return best;
}

/** Risk label derived only from backend anomalies + match status. */
export type RiskLevel = "High" | "Medium" | "Low" | "Safe";
export function riskFor(t: Transaction, anomalies: Anomaly[]): RiskLevel {
  const s = maxSeverity(anomalies);
  if (s === "HIGH") return "High";
  if (s === "MEDIUM") return "Medium";
  if (s === "LOW") return "Low";
  const ms = t.match_status as MatchStatus | null;
  return ms === "MATCHED" || ms === "LIKELY_MATCH" || ms === null ? "Safe" : "Medium";
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function labelize(k: string): string { return humanize(k); }
