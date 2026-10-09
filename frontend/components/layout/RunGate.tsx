"use client";
import type { ReactNode } from "react";
import { UploadCloud } from "lucide-react";
import { EmptyState, ErrorState, LinkButton, Skeleton } from "@/components/ui";
import { useRun } from "@/hooks/useRun";

/** Renders children only when a completed reconciliation run is available; otherwise shows loading/error/empty states. */
export function RunGate({ children, what = "results" }: { children: ReactNode; what?: string }) {
  const { run, loading, error, network, refresh } = useRun();
  if (loading) return <div className="space-y-4" aria-busy="true"><Skeleton className="h-24" /><Skeleton className="h-64" /></div>;
  if (error) return <ErrorState message={error} network={network} onRetry={refresh} />;
  if (!run || run.status !== "completed")
    return (
      <div className="rounded-xl border border-slate-200 bg-white shadow-card">
        <EmptyState icon={<UploadCloud className="h-6 w-6" />} title="No reconciliation has been run yet."
          message={`Upload a bank statement and an accounting export to see ${what}.`}
          action={<LinkButton href="/reconciliation">Start Reconciliation</LinkButton>} />
      </div>
    );
  return <>{children}</>;
}
