"use client";
import { useMemo, useState } from "react";
import { Card, CardHeader, ErrorState, PageHeader, Spinner } from "@/components/ui";
import { RunGate } from "@/components/layout/RunGate";
import { AnomalyTable } from "@/components/anomalies/AnomalyTable";
import { useRun } from "@/hooks/useRun";
import { useAnomalies } from "@/hooks/useAnomalies";
import { useTransactions } from "@/hooks/useTransactions";
import { ANOMALY_COLOR, ANOMALY_LABEL, ANOMALY_TYPES } from "@/lib/constants";
import type { AnomalyType, Severity } from "@/lib/types";
import { cn } from "@/lib/utils";

const CARD_LABEL: Record<AnomalyType, string> = {
  MISSING_TRANSACTION: "Missing Transactions", DUPLICATE_TRANSACTION: "Duplicates", TIMING_DIFFERENCE: "Timing Differences",
  AMOUNT_MISMATCH: "Amount Mismatches", HIGH_VALUE_MISMATCH: "High Value", POTENTIALLY_SUSPICIOUS: "Potentially Suspicious",
};

function Content() {
  const { runId } = useRun();
  const an = useAnomalies(runId);
  const tx = useTransactions(runId);
  const [type, setType] = useState<AnomalyType | "ALL">("ALL");
  const [sev, setSev] = useState<Severity | "ALL">("ALL");

  const counts = useMemo(() => {
    const c = {} as Record<AnomalyType, number>;
    for (const t of ANOMALY_TYPES) c[t] = an.anomalies.filter((a) => a.anomaly_type === t).length;
    return c;
  }, [an.anomalies]);
  const txns = useMemo(() => new Map((tx.data?.transactions ?? []).map((t) => [t.id, t])), [tx.data]);
  const list = an.anomalies.filter((a) => (type === "ALL" || a.anomaly_type === type) && (sev === "ALL" || a.severity === sev));

  if (an.loading) return <Card><Spinner label="Loading anomalies…" /></Card>;
  if (an.error) return <ErrorState message={an.error} network={an.network} onRetry={an.reload} />;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {ANOMALY_TYPES.map((t) => (
          <button key={t} onClick={() => setType(type === t ? "ALL" : t)} aria-pressed={type === t}
            className={cn("relative overflow-hidden rounded-xl border bg-white p-4 text-left shadow-card transition hover:border-brand-500", type === t ? "border-brand-600 ring-2 ring-brand-600/20" : "border-slate-200")}>
            <span className="absolute inset-y-0 left-0 w-1" style={{ background: ANOMALY_COLOR[t] }} aria-hidden />
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{CARD_LABEL[t]}</p>
            <p className="mt-1.5 text-2xl font-semibold tabular-nums text-navy-900">{counts[t]}</p>
          </button>
        ))}
      </div>
      <Card>
        <CardHeader title="Anomalies" subtitle={`${list.length} of ${an.anomalies.length} shown${type !== "ALL" ? ` · ${ANOMALY_LABEL[type]}` : ""}`}
          action={
            <div className="flex flex-wrap gap-2">
              <label className="sr-only" htmlFor="sev">Severity</label>
              <select id="sev" value={sev} onChange={(e) => setSev(e.target.value as Severity | "ALL")} className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm">
                <option value="ALL">All severities</option><option value="HIGH">High</option><option value="MEDIUM">Medium</option><option value="LOW">Low</option>
              </select>
              <label className="sr-only" htmlFor="atype">Anomaly type</label>
              <select id="atype" value={type} onChange={(e) => setType(e.target.value as AnomalyType | "ALL")} className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm">
                <option value="ALL">All types</option>{ANOMALY_TYPES.map((t) => <option key={t} value={t}>{ANOMALY_LABEL[t]}</option>)}
              </select>
            </div>} />
        <AnomalyTable anomalies={list} txns={txns} />
      </Card>
    </div>
  );
}

export default function AnomaliesPage() {
  return (
    <>
      <PageHeader title="Anomalies" subtitle="Discrepancies flagged by the reconciliation engine, highest severity first" />
      <RunGate what="anomalies"><Content /></RunGate>
    </>
  );
}
