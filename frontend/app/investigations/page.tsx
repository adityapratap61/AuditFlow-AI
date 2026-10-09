"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { AnomalyBadge, Card, EmptyState, ErrorState, PageHeader, Spinner } from "@/components/ui";
import { RunGate } from "@/components/layout/RunGate";
import { api, ApiError, errorMessage } from "@/lib/api";
import { useRun } from "@/hooks/useRun";
import type { Investigation } from "@/lib/types";
import { formatDateTime, pct } from "@/lib/utils";

function Content() {
  const { runId } = useRun();
  const [items, setItems] = useState<Investigation[] | null>(null);
  const [err, setErr] = useState<{ m: string; n: boolean } | null>(null);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!runId) return;
    let c = false; setItems(null); setErr(null);
    api.investigations({ run_id: runId, limit: 200 }).then((r) => !c && setItems(r)).catch((e) => !c && setErr({ m: errorMessage(e, "Unable to load investigations."), n: e instanceof ApiError && e.isNetwork }));
    return () => { c = true; };
  }, [runId, tick]);
  if (err) return <ErrorState message={err.m} network={err.n} onRetry={() => setTick((t) => t + 1)} />;
  if (!items) return <Card><Spinner label="Loading investigations…" /></Card>;
  if (items.length === 0) return <Card><EmptyState title="No investigations available." message="Investigations are created automatically during reconciliation for each anomaly." /></Card>;
  return (
    <Card><div className="table-wrap"><table className="w-full min-w-[44rem] text-left text-sm">
      <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th scope="col" className="px-4 py-3">Started</th><th scope="col" className="px-4 py-3">Classification</th><th scope="col" className="px-4 py-3 text-right">Confidence</th><th scope="col" className="px-4 py-3 text-right">Steps</th><th scope="col" className="px-4 py-3">Summary</th><th scope="col" className="px-4 py-3 text-right">Action</th></tr></thead>
      <tbody className="divide-y divide-slate-100">{items.map((i) => (
        <tr key={i.id} className="hover:bg-slate-50/70"><td className="whitespace-nowrap px-4 py-3 text-slate-600">{formatDateTime(i.created_at)}</td><td className="px-4 py-3"><AnomalyBadge type={i.conclusion} /></td>
          <td className="px-4 py-3 text-right tabular-nums">{pct(i.confidence)}</td><td className="px-4 py-3 text-right tabular-nums">{i.steps.length}</td>
          <td className="max-w-[22rem] px-4 py-3 text-slate-600"><span className="line-clamp-2">{i.explanation ?? "—"}</span></td>
          <td className="px-4 py-3 text-right"><Link href={`/investigations/${i.id}`} className="rounded-md bg-brand-50 px-2 py-1 text-xs font-medium text-brand-700 hover:bg-brand-100">View</Link></td></tr>))}</tbody>
    </table></div></Card>
  );
}
export default function InvestigationsPage() {
  return (<><PageHeader title="Investigations" subtitle="Agent investigation history for the current run" /><RunGate what="investigations"><Content /></RunGate></>);
}
