"use client";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { ArrowLeft, Sparkles } from "lucide-react";
import { AnomalyBadge, Badge, Button, Card, CardHeader, ErrorState, PageHeader, SeverityBadge, Spinner } from "@/components/ui";
import { InvestigationPanel, InvestigationRunning } from "@/components/investigation/InvestigationPanel";
import { api, ApiError, errorMessage } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";
import type { AnomalyDetail, Investigation, Transaction } from "@/lib/types";
import { formatDate, formatMoney, pct } from "@/lib/utils";

type Cmp = { label: string; bank: string; acc: string; same: boolean | null };

function compare(a: Transaction | null, b: Transaction | null): Cmp[] {
  const same = (x: unknown, y: unknown) => (a && b ? x === y : null);
  return [
    { label: "Amount", bank: a ? formatMoney(a.amount, a.currency) : "—", acc: b ? formatMoney(b.amount, b.currency) : "—", same: same(a?.amount, b?.amount) },
    { label: "Date", bank: formatDate(a?.date), acc: formatDate(b?.date), same: same(a?.date, b?.date) },
    { label: "Description", bank: a?.raw_description ?? "—", acc: b?.raw_description ?? "—", same: same(a?.normalized_description, b?.normalized_description) },
    { label: "Reference", bank: a?.reference ?? "—", acc: b?.reference ?? "—", same: a && b && a.reference && b.reference ? a.reference === b.reference : null },
  ];
}

function Detail() {
  const { id } = useParams<{ id: string }>();
  const search = useSearchParams();
  const toast = useToast();
  const [a, setA] = useState<AnomalyDetail | null>(null);
  const [inv, setInv] = useState<Investigation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ msg: string; network: boolean } | null>(null);
  const [running, setRunning] = useState(false);
  const [invError, setInvError] = useState<string | null>(null);
  const auto = useRef(false);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const d = await api.anomaly(id); setA(d);
      if (d.investigation_id) { try { setInv(await api.investigation(d.investigation_id)); } catch { /* optional */ } }
    } catch (e) { setError({ msg: errorMessage(e, "Unable to load this anomaly."), network: e instanceof ApiError && e.isNetwork }); }
    finally { setLoading(false); }
  }, [id]);
  useEffect(() => { void load(); }, [load]);

  const investigate = useCallback(async () => {
    setRunning(true); setInvError(null);
    try {
      const r = await api.investigate(id); setInv(r);
      setA((p) => (p ? { ...p, status: "INVESTIGATED", investigation_id: r.id } : p));
      toast.success("Investigation complete.");
    } catch (e) {
      setInvError(e instanceof ApiError && e.isNetwork ? e.message : "AI investigation could not be completed. The deterministic reconciliation result is still available.");
      toast.error("AI investigation could not be completed.");
    } finally { setRunning(false); }
  }, [id, toast]);

  useEffect(() => {
    if (a && search.get("investigate") === "1" && !auto.current) { auto.current = true; void investigate(); }
  }, [a, search, investigate]);

  if (loading) return <Card><Spinner label="Loading anomaly…" /></Card>;
  if (error || !a) return <ErrorState message={error?.msg ?? "Anomaly not found."} network={error?.network} onRetry={load} />;

  const bankSide = a.source === "BANK" ? a.transaction : a.related_transaction;
  const accSide = a.source === "BANK" ? a.related_transaction : a.transaction;
  const rows = compare(bankSide, accSide);
  const dims = (a.details ?? {}) as Record<string, unknown>;

  return (
    <div className="space-y-6">
      <Link href="/anomalies" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-navy-900"><ArrowLeft className="h-4 w-4" aria-hidden />Back to anomalies</Link>
      <PageHeader title={a.transaction ? `${a.transaction.description}` : "Anomaly"} subtitle={a.transaction ? `${formatMoney(a.transaction.amount, a.transaction.currency)} · ${formatDate(a.transaction.date)}` : undefined}
        action={<Button onClick={investigate} loading={running}><Sparkles className="h-4 w-4" aria-hidden />{inv ? "Re-run AI Investigation" : "Investigate with AI"}</Button>} />

      <div className="grid gap-4 sm:grid-cols-4">
        <Card className="p-4"><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Anomaly Type</p><div className="mt-2"><AnomalyBadge type={a.anomaly_type} /></div></Card>
        <Card className="p-4"><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Risk Level</p><div className="mt-2"><SeverityBadge severity={a.severity} /></div></Card>
        <Card className="p-4"><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Confidence</p><p className="mt-1 text-xl font-semibold tabular-nums text-navy-900">{pct(a.confidence)}</p></Card>
        <Card className="p-4"><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Status</p><div className="mt-2"><Badge tone={a.status === "INVESTIGATED" ? "teal" : "slate"}>{a.status === "INVESTIGATED" ? "Investigated" : "Open"}</Badge></div></Card>
      </div>

      <Card>
        <CardHeader title="Why was this flagged?" />
        <div className="space-y-3 p-5">
          <p className="text-sm text-slate-700">{a.description}</p>
          {a.initial_type && a.initial_type !== a.anomaly_type && <p className="text-xs text-slate-500">Initially flagged as <AnomalyBadge type={a.initial_type} />, reclassified after investigation.</p>}
          {Object.keys(dims).length > 0 && (
            <dl className="grid gap-x-8 sm:grid-cols-2">
              {Object.entries(dims).filter(([, v]) => v === null || typeof v !== "object").map(([k, v]) => (
                <div key={k} className="flex justify-between gap-4 border-t border-slate-100 py-2 text-sm"><dt className="text-slate-500">{k.replace(/_/g, " ")}</dt><dd className="font-medium text-navy-900">{String(v)}</dd></div>
              ))}
            </dl>
          )}
        </div>
      </Card>

      <Card>
        <CardHeader title="Bank vs Accounting" subtitle={accSide ? undefined : "No accounting record is linked to this item."} />
        <div className="table-wrap"><table className="w-full min-w-[34rem] text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th scope="col" className="px-5 py-3"> </th><th scope="col" className="px-5 py-3">Bank record</th><th scope="col" className="px-5 py-3">Accounting record</th><th scope="col" className="px-5 py-3">Result</th></tr></thead>
          <tbody className="divide-y divide-slate-100">{rows.map((r) => (
            <tr key={r.label}><th scope="row" className="px-5 py-3 font-medium text-slate-500">{r.label}</th><td className="px-5 py-3 text-navy-900">{r.bank}</td><td className="px-5 py-3 text-navy-900">{r.acc}</td>
              <td className="px-5 py-3">{r.same === null ? <span className="text-slate-400">— n/a</span> : r.same ? <span className="font-medium text-emerald-700">✓ Match</span> : <span className="font-medium text-amber-700">⚠ Differs</span>}</td></tr>))}</tbody>
        </table></div>
      </Card>

      {a.explanation && !inv && !running && (
        <Card><CardHeader title="AI Interpretation" /><p className="p-5 text-sm leading-relaxed text-slate-700">{a.explanation}</p></Card>
      )}
      {invError && <ErrorState message={invError} onRetry={investigate} />}
      {running ? <InvestigationRunning /> : inv ? <InvestigationPanel inv={inv} bank={bankSide} />
        : !invError && <Card><div className="flex flex-col items-center gap-3 p-8 text-center"><p className="text-sm text-slate-600">Run the AI agent to search for counterpart transactions and see its full evidence trail.</p><Button onClick={investigate}><Sparkles className="h-4 w-4" aria-hidden />Investigate with AI</Button></div></Card>}
    </div>
  );
}

export default function AnomalyDetailPage() {
  return <Suspense fallback={<Spinner />}><Detail /></Suspense>;
}
