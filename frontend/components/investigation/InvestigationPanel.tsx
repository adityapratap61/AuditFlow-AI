"use client";
import { AlertTriangle, Brain, CheckCircle2, Cpu, Lightbulb, Loader2, Wrench } from "lucide-react";
import { AnomalyBadge, Badge, Card, CardHeader } from "@/components/ui";
import { TOOL_LABEL } from "@/lib/constants";
import type { Investigation, Transaction } from "@/lib/types";
import { formatDate, formatDateTime, formatMoney, humanize, pct } from "@/lib/utils";

/** Renders only what the backend returned: steps, evidence, conclusion, explanation. */
export function InvestigationRunning() {
  return (
    <Card>
      <CardHeader title="AI Investigation" />
      <div role="status" className="flex items-center gap-3 p-6 text-sm text-slate-600">
        <Loader2 className="h-5 w-5 animate-spin text-brand-600" aria-hidden />
        <div><p className="font-medium text-navy-900">Investigating…</p><p className="text-xs text-slate-500">The agent is searching, comparing and evaluating candidates. Steps appear when the backend returns them.</p></div>
      </div>
    </Card>
  );
}

function fmt(v: unknown, key: string): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (typeof v === "number") {
    if (/similarity|score/.test(key)) return `${Math.round(v)}%`;
    if (/days/.test(key)) return `${v} day${Math.abs(v) === 1 ? "" : "s"}`;
    if (/amount|difference/.test(key) && !/days/.test(key)) return formatMoney(v);
    return String(v);
  }
  if (typeof v === "string") return /^\d{4}-\d{2}-\d{2}/.test(v) ? formatDate(v) : v;
  return JSON.stringify(v);
}

function pickFacts(inv: Investigation, bank: Transaction | null | undefined) {
  const facts: { k: string; v: string }[] = [];
  const cmp = inv.evidence?.comparison ?? {};
  const tx = inv.evidence?.transaction as Record<string, unknown> | undefined;
  if (tx?.amount != null) facts.push({ k: "Amount", v: formatMoney(Number(tx.amount)) });
  else if (bank) facts.push({ k: "Amount", v: formatMoney(bank.amount, bank.currency) });
  for (const [k, v] of Object.entries(cmp)) {
    if (v !== null && typeof v === "object") continue;
    facts.push({ k: humanize(k), v: fmt(v, k) });
  }
  return facts;
}

export function InvestigationPanel({ inv, bank }: { inv: Investigation; bank?: Transaction | null }) {
  const facts = pickFacts(inv, bank);
  const d = inv.explanation_detail;
  const failed = inv.status !== "completed";
  const sourceLabel = inv.explanation_source === "ollama" ? "Local LLM (Ollama)" : "Deterministic engine";

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader title="AI Investigation" subtitle={`Started ${formatDateTime(inv.created_at)}${inv.completed_at ? ` · finished ${formatDateTime(inv.completed_at)}` : ""}`}
          action={failed ? <Badge tone="amber">Status: {inv.status}</Badge> : <span className="inline-flex items-center gap-1 text-sm font-medium text-emerald-700"><CheckCircle2 className="h-4 w-4" aria-hidden />Investigation Complete</span>} />
        <div className="grid gap-6 p-5 md:grid-cols-3">
          <div><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Classification</p><div className="mt-2"><AnomalyBadge type={inv.conclusion} /></div></div>
          <div><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Confidence</p><p className="mt-1 text-2xl font-semibold tabular-nums text-navy-900">{pct(inv.confidence)}</p></div>
          <div><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Explanation source</p><p className="mt-2 inline-flex items-center gap-1.5 text-sm text-slate-700"><Cpu className="h-4 w-4 text-slate-400" aria-hidden />{sourceLabel}</p></div>
        </div>
      </Card>

      <Card>
        <CardHeader title="Investigation Steps" subtitle={`${inv.steps.length} step${inv.steps.length === 1 ? "" : "s"} recorded by the agent`} />
        {inv.steps.length === 0 ? <p className="p-5 text-sm text-slate-500">The backend did not record any steps for this investigation.</p> : (
          <ol className="divide-y divide-slate-100">
            {[...inv.steps].sort((a, b) => a.step_number - b.step_number).map((s) => (
              <li key={s.id} className="flex gap-3 px-5 py-3.5">
                <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" aria-hidden />
                <div className="min-w-0">
                  <p className="text-sm font-medium text-navy-900">{s.step_number}. {TOOL_LABEL[s.tool] ?? humanize(s.tool)} <span className="ml-1 font-mono text-xs font-normal text-slate-400"><Wrench className="mr-0.5 inline h-3 w-3" aria-hidden />{s.tool}</span></p>
                  <p className="mt-0.5 text-sm text-slate-600">{s.result_summary}</p>
                  {s.decision && <p className="mt-0.5 text-xs text-slate-500">Decision: {s.decision}</p>}
                </div>
              </li>
            ))}
          </ol>
        )}
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader title="Facts" subtitle="Deterministic values from the evidence" />
          {facts.length === 0 ? <p className="p-5 text-sm text-slate-500">No comparison data available.</p> : (
            <dl className="divide-y divide-slate-100 px-5">{facts.map((f) => <div key={f.k} className="flex justify-between gap-4 py-2.5 text-sm"><dt className="text-slate-500">{f.k}</dt><dd className="text-right font-medium text-navy-900">{f.v}</dd></div>)}</dl>
          )}
          {d?.evidence_points && d.evidence_points.length > 0 && (
            <div className="border-t border-slate-100 p-5"><p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Evidence</p>
              <ul className="space-y-1.5 text-sm text-slate-700">{d.evidence_points.map((p, i) => <li key={i} className="flex gap-2"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-teal-600" aria-hidden />{p}</li>)}</ul></div>
          )}
        </Card>
        <Card>
          <CardHeader title="AI Interpretation" subtitle={inv.explanation_source === "ollama" ? "Phrased by local LLM, validated against evidence" : "Generated from structured evidence"} />
          <div className="space-y-4 p-5">
            <div className="flex gap-3"><Brain className="mt-0.5 h-5 w-5 shrink-0 text-brand-600" aria-hidden /><p className="text-sm leading-relaxed text-slate-700">{inv.explanation ?? "No explanation was provided."}</p></div>
            {d?.inference && d.inference !== inv.explanation && <p className="rounded-lg bg-slate-50 p-3 text-sm text-slate-700"><span className="font-medium">Inference: </span>{d.inference}</p>}
            {d?.recommended_action && (
              <div className="flex gap-3 rounded-lg border border-amber-200 bg-amber-50 p-3"><Lightbulb className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" aria-hidden />
                <div><p className="text-xs font-semibold uppercase tracking-wide text-amber-800">Recommendation</p><p className="mt-0.5 text-sm text-amber-900">{d.recommended_action}</p></div></div>
            )}
            <p className="flex items-start gap-1.5 text-xs text-slate-500"><AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />AuditFlow AI flags items for manual verification; it never confirms fraud.</p>
          </div>
        </Card>
      </div>
    </div>
  );
}
