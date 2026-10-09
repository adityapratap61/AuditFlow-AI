"use client";
import { RefreshCw } from "lucide-react";
import { Button, LinkButton, PageHeader, Spinner } from "@/components/ui";
import { RunGate } from "@/components/layout/RunGate";
import { SummaryView } from "@/components/dashboard/SummaryView";
import { useRun } from "@/hooks/useRun";
import { useAnomalies } from "@/hooks/useAnomalies";

function Content() {
  const { run, runId } = useRun();
  const { anomalies, loading } = useAnomalies(runId);
  if (!run) return null;
  if (loading && anomalies.length === 0 && run.anomalies.length === 0) return <Spinner label="Loading dashboard…" />;
  return <SummaryView run={run} anomalies={anomalies.length ? anomalies : run.anomalies} />;
}

export default function DashboardPage() {
  const { refresh } = useRun();
  return (
    <>
      <PageHeader title="Dashboard" subtitle="Reconciliation overview for the latest run"
        action={<div className="flex gap-2"><Button variant="secondary" onClick={refresh}><RefreshCw className="h-4 w-4" aria-hidden />Refresh</Button><LinkButton href="/reconciliation">New Reconciliation</LinkButton></div>} />
      <RunGate what="the dashboard"><Content /></RunGate>
    </>
  );
}
