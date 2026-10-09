"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, EmptyState, ErrorState, LinkButton, PageHeader, Spinner } from "@/components/ui";
import { DownloadButtons } from "@/components/reports/ReportView";
import { api, ApiError, errorMessage } from "@/lib/api";
import { useRun } from "@/hooks/useRun";
import type { ReconciliationResult } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

export default function ReportsPage() {
  const { runId } = useRun();
  const [runs, setRuns] = useState<ReconciliationResult[] | null>(null);
  const [err, setErr] = useState<{ m: string; n: boolean } | null>(null);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let c = false; setRuns(null); setErr(null);
    api.listRuns(50, 0).then((r) => !c && setRuns(r.items.filter((x) => x.status === "completed")))
      .catch((e) => !c && setErr({ m: errorMessage(e, "Unable to load reports."), n: e instanceof ApiError && e.isNetwork }));
    return () => { c = true; };
  }, [tick]);
  return (
    <>
      <PageHeader title="Reports" subtitle="Reconciliation reports for completed runs" />
      {err ? <ErrorState message={err.m} network={err.n} onRetry={() => setTick((t) => t + 1)} />
        : !runs ? <Card><Spinner label="Loading reports…" /></Card>
        : runs.length === 0 ? <Card><EmptyState title="No reconciliation has been run yet." message="Reports are available once a reconciliation completes." action={<LinkButton href="/reconciliation">Start Reconciliation</LinkButton>} /></Card>
        : (
          <div className="space-y-3">{runs.map((r) => (
            <Card key={r.run_id} className="flex flex-wrap items-center justify-between gap-3 p-4">
              <div><p className="text-sm font-medium text-navy-900">{r.bank_filename} ↔ {r.accounting_filename}{r.run_id === runId && <span className="ml-2 rounded-full bg-brand-50 px-2 py-0.5 text-xs text-brand-700">Current</span>}</p>
                <p className="text-xs text-slate-500">{formatDateTime(r.completed_at ?? r.created_at)} · run {r.run_id.slice(0, 8)}</p></div>
              <div className="flex flex-wrap items-center gap-2"><Link href={`/reports/${r.run_id}`} className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-navy-900 hover:bg-slate-50">View report</Link><DownloadButtons runId={r.run_id} /></div>
            </Card>))}</div>)}
    </>
  );
}
