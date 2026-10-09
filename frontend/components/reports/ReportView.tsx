"use client";
import Link from "next/link";
import { useState } from "react";
import { Download, FileJson, FileSpreadsheet } from "lucide-react";
import { AnomalyBadge, Button, Card, CardHeader, EmptyState, SeverityBadge, Stat } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";
import { ANOMALY_LABEL, ANOMALY_TYPES } from "@/lib/constants";
import type { Report, ReportAnomalyRow } from "@/lib/types";
import { downloadBlob, formatDateTime, formatMoney, pct } from "@/lib/utils";

export function DownloadButtons({ runId }: { runId: string }) {
  const toast = useToast();
  const [busy, setBusy] = useState<"json" | "csv" | null>(null);
  const go = async (f: "json" | "csv") => {
    setBusy(f);
    try {
      const blob = await api.reportBlob(runId, f);
      downloadBlob(blob, `auditflow_report_${runId}.${f}`);
      toast.success(`${f.toUpperCase()} report downloaded.`);
    } catch (e) { toast.error(errorMessage(e, "Report could not be generated.")); }
    finally { setBusy(null); }
  };
  return (
    <div className="flex flex-wrap gap-2">
      <Button variant="secondary" loading={busy === "json"} disabled={busy !== null} onClick={() => go("json")}><FileJson className="h-4 w-4" aria-hidden />Download JSON</Button>
      <Button loading={busy === "csv"} disabled={busy !== null} onClick={() => go("csv")}><FileSpreadsheet className="h-4 w-4" aria-hidden />Download CSV</Button>
    </div>
  );
}

function AnomalyRows({ rows, empty }: { rows: ReportAnomalyRow[]; empty: string }) {
  if (rows.length === 0) return <EmptyState title={empty} />;
  return (
    <div className="table-wrap"><table className="w-full min-w-[40rem] text-left text-sm">
      <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th scope="col" className="px-4 py-3">Severity</th><th scope="col" className="px-4 py-3">Transaction</th><th scope="col" className="px-4 py-3 text-right">Amount</th><th scope="col" className="px-4 py-3">Type</th><th scope="col" className="px-4 py-3 text-right">Confidence</th><th scope="col" className="px-4 py-3 text-right">Action</th></tr></thead>
      <tbody className="divide-y divide-slate-100">{rows.map((r) => (
        <tr key={r.anomaly_id}><td className="px-4 py-3"><SeverityBadge severity={r.severity} /></td><td className="max-w-[18rem] truncate px-4 py-3 font-medium text-navy-900">{r.transaction?.description ?? "—"}</td>
          <td className="whitespace-nowrap px-4 py-3 text-right tabular-nums">{r.transaction ? formatMoney(r.transaction.amount) : "—"}</td><td className="px-4 py-3"><AnomalyBadge type={r.type} /></td>
          <td className="px-4 py-3 text-right tabular-nums">{pct(r.confidence)}</td>
          <td className="px-4 py-3 text-right"><Link href={`/anomalies/${r.anomaly_id}`} className="text-xs font-medium text-brand-600 hover:underline">Open</Link></td></tr>))}</tbody>
    </table></div>
  );
}

export function ReportView({ report }: { report: Report }) {
  const t = report.totals;
  const recs = report.investigation_summaries;
  return (
    <div className="space-y-6">
      <Card className="p-5">
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
          <span>Generated {formatDateTime(report.report_metadata.generated_at)}</span>
          <span>{report.report_metadata.bank_file} ↔ {report.report_metadata.accounting_file}</span>
        </div>
        {report.narrative && <p className="mt-3 text-sm leading-relaxed text-slate-700">{report.narrative}</p>}
      </Card>

      <section aria-label="Reconciliation summary">
        <h2 className="mb-3 text-sm font-semibold text-navy-900">Reconciliation Summary</h2>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
          <Stat label="Bank" value={t.bank_transactions} tone="blue" /><Stat label="Accounting" value={t.accounting_transactions} tone="blue" />
          <Stat label="Matched" value={t.matched} tone="green" /><Stat label="Likely" value={t.likely_matches} tone="teal" />
          <Stat label="Review" value={t.review_required} tone="amber" /><Stat label="Unmatched" value={t.unmatched} tone="red" />
          <Stat label="Match Rate" value={pct(t.match_rate)} tone="green" />
        </div>
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card><CardHeader title="Anomaly Summary" />
          <dl className="divide-y divide-slate-100 px-5">{ANOMALY_TYPES.map((a) => <div key={a} className="flex justify-between py-2.5 text-sm"><dt className="text-slate-600">{ANOMALY_LABEL[a]}</dt><dd className="font-medium tabular-nums text-navy-900">{report.anomaly_counts[a] ?? 0}</dd></div>)}</dl></Card>
        <Card><CardHeader title="Severity" />
          <dl className="divide-y divide-slate-100 px-5">{(["HIGH", "MEDIUM", "LOW"] as const).map((s) => <div key={s} className="flex items-center justify-between py-2.5 text-sm"><dt><SeverityBadge severity={s} /></dt><dd className="font-medium tabular-nums text-navy-900">{report.severity_counts[s] ?? 0}</dd></div>)}</dl></Card>
      </div>

      <Card><CardHeader title="High-Risk Transactions" subtitle="High-value mismatches" /><AnomalyRows rows={report.high_value_mismatches} empty="No high-value mismatches." /></Card>
      <Card><CardHeader title="Potentially Suspicious" subtitle="Flagged for manual verification — not confirmed fraud" /><AnomalyRows rows={report.suspicious_transactions} empty="No potentially suspicious transactions." /></Card>

      <Card><CardHeader title="Investigation Results" subtitle={`${recs.length} investigation${recs.length === 1 ? "" : "s"}`} />
        {recs.length === 0 ? <EmptyState title="No investigations available." /> : (
          <ul className="divide-y divide-slate-100">{recs.map((i) => (
            <li key={i.investigation_id} className="flex flex-wrap items-start justify-between gap-3 px-5 py-3.5">
              <div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><AnomalyBadge type={i.conclusion} /><span className="text-xs text-slate-500">{pct(i.confidence)} confidence · {i.steps} steps</span></div><p className="mt-1.5 line-clamp-2 text-sm text-slate-600">{i.explanation ?? "—"}</p></div>
              <Link href={`/investigations/${i.investigation_id}`} className="text-xs font-medium text-brand-600 hover:underline">View</Link>
            </li>))}</ul>)}
      </Card>
      <p className="text-xs text-slate-500">{report.disclaimer}</p>
    </div>
  );
}
