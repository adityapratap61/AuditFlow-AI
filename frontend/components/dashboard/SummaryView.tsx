"use client";
import { Card, CardHeader, Stat } from "@/components/ui";
import { AnomalyChart, MatchStatusChart, RiskChart } from "@/components/charts/Charts";
import type { Anomaly, ReconciliationResult } from "@/lib/types";
import { pct, toInt } from "@/lib/utils";

const OVERALL: Record<string, { text: string; cls: string }> = {
  RECONCILED: { text: "Reconciled", cls: "bg-emerald-50 text-emerald-700" },
  REVIEW_NEEDED: { text: "Review needed", cls: "bg-amber-50 text-amber-800" },
  ATTENTION_REQUIRED: { text: "Attention required", cls: "bg-red-50 text-red-700" },
};

export function SummaryView({ run, anomalies, showCharts = true }: { run: ReconciliationResult; anomalies: Anomaly[]; showCharts?: boolean }) {
  const s = run.summary;
  if (!s) return null;
  const overall = run.overall_status ? OVERALL[run.overall_status] : null;
  return (
    <div className="space-y-6">
      {(run.narrative || overall) && (
        <Card className="p-5">
          <div className="flex flex-wrap items-center gap-3">
            {overall && <span className={`rounded-full px-3 py-1 text-xs font-semibold ${overall.cls}`}>{overall.text}</span>}
            {run.processing_time != null && <span className="text-xs text-slate-500">Processed in {run.processing_time.toFixed(2)}s · match rate {pct(s.match_rate)}</span>}
          </div>
          {run.narrative && <p className="mt-3 text-sm leading-relaxed text-slate-700">{run.narrative}</p>}
        </Card>
      )}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Stat label="Bank Transactions" value={toInt(s.total_bank_transactions).toLocaleString("en-IN")} tone="blue" />
        <Stat label="Accounting Transactions" value={toInt(s.total_accounting_transactions).toLocaleString("en-IN")} tone="blue" />
        <Stat label="Matched" value={toInt(s.matched).toLocaleString("en-IN")} tone="green" />
        <Stat label="Likely Matches" value={toInt(s.likely_matches).toLocaleString("en-IN")} tone="teal" />
        <Stat label="Review Required" value={toInt(s.review_required).toLocaleString("en-IN")} tone="amber" />
        <Stat label="Unmatched" value={toInt(s.unmatched).toLocaleString("en-IN")} tone="red" hint={toInt(s.unmatched_accounting) ? `+${s.unmatched_accounting} accounting-only` : undefined} />
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Total Anomalies" value={toInt(s.total_anomalies)} tone="slate" />
        <Stat label="High Risk" value={toInt(s.high_risk)} tone="red" />
        <Stat label="Total Transactions" value={(toInt(s.total_bank_transactions) + toInt(s.total_accounting_transactions)).toLocaleString("en-IN")} tone="slate" hint="Bank + accounting" />
        <Stat label="Match Rate" value={pct(s.match_rate)} tone="green" />
      </div>
      {showCharts && (
        <div className="grid gap-4 lg:grid-cols-3">
          <Card><CardHeader title="Transaction Match Status" subtitle="Bank transactions" /><div className="p-3"><MatchStatusChart summary={s} /></div></Card>
          <Card><CardHeader title="Anomaly Distribution" /><div className="p-3"><AnomalyChart summary={s} /></div></Card>
          <Card><CardHeader title="Risk Distribution" subtitle="By severity" /><div className="p-3"><RiskChart anomalies={anomalies} /></div></Card>
        </div>
      )}
    </div>
  );
}
