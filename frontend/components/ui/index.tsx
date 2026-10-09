"use client";
import Link from "next/link";
import { AlertTriangle, Inbox, Loader2, WifiOff } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/utils";
import { ANOMALY_LABEL, MATCH_LABEL } from "@/lib/constants";
import type { AnomalyType, MatchStatus, Severity } from "@/lib/types";
import type { RiskLevel } from "@/lib/utils";

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <section className={cn("rounded-xl border border-slate-200 bg-white shadow-card", className)}>{children}</section>;
}
export function CardHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-2 border-b border-slate-100 px-5 py-4">
      <div><h2 className="text-sm font-semibold text-navy-900">{title}</h2>{subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}</div>
      {action}
    </div>
  );
}
export function PageHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div><h1 className="text-2xl font-semibold tracking-tight text-navy-900">{title}</h1>{subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}</div>
      {action}
    </div>
  );
}

type Variant = "primary" | "secondary" | "ghost" | "danger";
const VARIANTS: Record<Variant, string> = {
  primary: "bg-brand-600 text-white hover:bg-brand-700 shadow-sm",
  secondary: "bg-white text-navy-900 border border-slate-300 hover:bg-slate-50",
  ghost: "text-slate-600 hover:bg-slate-100",
  danger: "bg-red-600 text-white hover:bg-red-700",
};
export function Button({ variant = "primary", loading, className, children, disabled, ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; loading?: boolean }) {
  return (
    <button {...rest} disabled={disabled || loading}
      className={cn("inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50", VARIANTS[variant], className)}>
      {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}{children}
    </button>
  );
}
export function LinkButton({ href, variant = "primary", className, children }: { href: string; variant?: Variant; className?: string; children: ReactNode }) {
  return <Link href={href} className={cn("inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition", VARIANTS[variant], className)}>{children}</Link>;
}

const TONES = {
  green: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  teal: "bg-teal-50 text-teal-700 ring-teal-600/20",
  amber: "bg-amber-50 text-amber-800 ring-amber-600/25",
  orange: "bg-orange-50 text-orange-700 ring-orange-600/25",
  red: "bg-red-50 text-red-700 ring-red-600/20",
  slate: "bg-slate-100 text-slate-600 ring-slate-500/20",
  blue: "bg-brand-50 text-brand-700 ring-brand-600/20",
  purple: "bg-violet-50 text-violet-700 ring-violet-600/20",
};
export type Tone = keyof typeof TONES;
export function Badge({ tone = "slate", children }: { tone?: Tone; children: ReactNode }) {
  return <span className={cn("inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset", TONES[tone])}>{children}</span>;
}
const MATCH_TONE: Record<MatchStatus, Tone> = { MATCHED: "green", LIKELY_MATCH: "teal", REVIEW_REQUIRED: "amber", UNMATCHED: "red" };
export function MatchBadge({ status }: { status: MatchStatus | null }) {
  return status ? <Badge tone={MATCH_TONE[status]}>{MATCH_LABEL[status]}</Badge> : <span className="text-slate-400">—</span>;
}
const SEV_TONE: Record<Severity, Tone> = { HIGH: "red", MEDIUM: "amber", LOW: "green" };
export function SeverityBadge({ severity }: { severity: Severity }) { return <Badge tone={SEV_TONE[severity]}>{severity}</Badge>; }
const TYPE_TONE: Record<AnomalyType, Tone> = {
  MISSING_TRANSACTION: "red", DUPLICATE_TRANSACTION: "purple", TIMING_DIFFERENCE: "amber",
  AMOUNT_MISMATCH: "orange", HIGH_VALUE_MISMATCH: "red", POTENTIALLY_SUSPICIOUS: "slate",
};
export function AnomalyBadge({ type }: { type: AnomalyType | null | undefined }) {
  return type ? <Badge tone={TYPE_TONE[type]}>{ANOMALY_LABEL[type]}</Badge> : <span className="text-slate-400">—</span>;
}
const RISK_TONE: Record<RiskLevel, Tone> = { High: "red", Medium: "amber", Low: "teal", Safe: "green" };
export function RiskBadge({ risk }: { risk: RiskLevel }) { return <Badge tone={RISK_TONE[risk]}>{risk === "High" ? "High Risk" : risk}</Badge>; }

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div role="status" className="flex items-center justify-center gap-2 py-16 text-sm text-slate-500">
      <Loader2 className="h-5 w-5 animate-spin text-brand-600" aria-hidden />{label}
    </div>
  );
}
export function Skeleton({ className }: { className?: string }) { return <div className={cn("animate-pulse rounded-lg bg-slate-200/70", className)} />; }

export function EmptyState({ title, message, action, icon }: { title: string; message?: string; action?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
      <div className="mb-3 rounded-full bg-slate-100 p-3 text-slate-400">{icon ?? <Inbox className="h-6 w-6" aria-hidden />}</div>
      <p className="text-sm font-medium text-navy-900">{title}</p>
      {message && <p className="mt-1 max-w-md text-sm text-slate-500">{message}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
export function ErrorState({ message, network, onRetry }: { message: string; network?: boolean; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex flex-col items-center rounded-xl border border-red-200 bg-red-50/60 px-6 py-10 text-center">
      <div className="mb-3 rounded-full bg-red-100 p-3 text-red-600">{network ? <WifiOff className="h-6 w-6" aria-hidden /> : <AlertTriangle className="h-6 w-6" aria-hidden />}</div>
      <p className="max-w-lg text-sm font-medium text-red-800">{message}</p>
      {onRetry && <Button variant="secondary" className="mt-4" onClick={onRetry}>Try again</Button>}
    </div>
  );
}
export function Stat({ label, value, tone = "slate", hint }: { label: string; value: ReactNode; tone?: "slate" | "green" | "teal" | "amber" | "red" | "blue"; hint?: string }) {
  const bar = { slate: "bg-slate-300", green: "bg-emerald-500", teal: "bg-teal-500", amber: "bg-amber-500", red: "bg-red-500", blue: "bg-brand-500" }[tone];
  return (
    <div className="relative overflow-hidden rounded-xl border border-slate-200 bg-white p-4 shadow-card">
      <span className={cn("absolute inset-y-0 left-0 w-1", bar)} aria-hidden />
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1.5 text-2xl font-semibold tabular-nums text-navy-900">{value}</p>
      {hint && <p className="mt-0.5 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}
export function Logo({ light }: { light?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2">
      <span className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-brand-600 to-teal-500 text-white" aria-hidden>
        <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 7h10M4 12h16M4 17h10" /><path d="m17 5 3 2-3 2" /></svg>
      </span>
      <span className={cn("text-lg font-semibold tracking-tight", light ? "text-white" : "text-navy-900")}>AuditFlow <span className="text-teal-500">AI</span></span>
    </span>
  );
}
