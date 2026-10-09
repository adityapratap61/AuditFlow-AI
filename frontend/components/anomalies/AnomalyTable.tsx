"use client";
import Link from "next/link";
import { EmptyState, AnomalyBadge, SeverityBadge } from "@/components/ui";
import type { Anomaly, Transaction } from "@/lib/types";
import { formatMoney, pct } from "@/lib/utils";

export function AnomalyTable({ anomalies, txns }: { anomalies: Anomaly[]; txns: Map<string, Transaction> }) {
  if (anomalies.length === 0) return <EmptyState title="No anomalies detected." message="Nothing matches the current selection." />;
  return (
    <div className="table-wrap">
      <table className="w-full min-w-[56rem] text-left text-sm">
        <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th scope="col" className="px-4 py-3">Severity</th><th scope="col" className="px-4 py-3">Transaction</th>
            <th scope="col" className="px-4 py-3 text-right">Amount</th><th scope="col" className="px-4 py-3">Type</th>
            <th scope="col" className="px-4 py-3">Reason</th><th scope="col" className="px-4 py-3 text-right">Confidence</th>
            <th scope="col" className="px-4 py-3 text-right">Action</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {anomalies.map((a) => {
            const t = txns.get(a.transaction_id);
            return (
              <tr key={a.id} className="hover:bg-slate-50/70">
                <td className="px-4 py-3"><SeverityBadge severity={a.severity} /></td>
                <td className="max-w-[14rem] px-4 py-3"><p className="truncate font-medium text-navy-900" title={t?.raw_description}>{t?.description ?? "—"}</p><p className="text-xs text-slate-400">{a.source === "BANK" ? "Bank" : "Accounting"}</p></td>
                <td className="whitespace-nowrap px-4 py-3 text-right font-medium tabular-nums">{t ? formatMoney(t.amount, t.currency) : "—"}</td>
                <td className="px-4 py-3"><AnomalyBadge type={a.anomaly_type} /></td>
                <td className="max-w-[20rem] px-4 py-3 text-slate-600"><span className="line-clamp-2" title={a.description}>{a.description}</span></td>
                <td className="px-4 py-3 text-right tabular-nums">{pct(a.confidence)}</td>
                <td className="whitespace-nowrap px-4 py-3 text-right">
                  <Link href={`/anomalies/${a.id}`} className="mr-1 rounded-md px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100">View</Link>
                  <Link href={`/anomalies/${a.id}?investigate=1`} className="rounded-md bg-brand-50 px-2 py-1 text-xs font-medium text-brand-700 hover:bg-brand-100">Investigate</Link>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
