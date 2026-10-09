"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { Card, ErrorState, PageHeader, Spinner } from "@/components/ui";
import { DownloadButtons, ReportView } from "@/components/reports/ReportView";
import { api, ApiError, errorMessage } from "@/lib/api";
import type { Report } from "@/lib/types";

export default function ReportPage() {
  const { id } = useParams<{ id: string }>();
  const [report, setReport] = useState<Report | null>(null);
  const [err, setErr] = useState<{ m: string; n: boolean } | null>(null);
  const load = useCallback(async () => {
    setErr(null); setReport(null);
    try { setReport(await api.report(id)); }
    catch (e) { setErr({ m: errorMessage(e, "Report could not be generated."), n: e instanceof ApiError && e.isNetwork }); }
  }, [id]);
  useEffect(() => { void load(); }, [load]);
  return (
    <div>
      <Link href="/reports" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-navy-900"><ArrowLeft className="h-4 w-4" aria-hidden />All reports</Link>
      <PageHeader title="Reconciliation Report" subtitle={`Run ${id.slice(0, 8)}`} action={<DownloadButtons runId={id} />} />
      {err ? <ErrorState message={err.m} network={err.n} onRetry={load} /> : !report ? <Card><Spinner label="Generating report…" /></Card> : <ReportView report={report} />}
    </div>
  );
}
