"use client";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ANOMALY_COLOR, ANOMALY_SHORT, ANOMALY_TYPES, MATCH_COLOR, MATCH_LABEL, SEVERITY_COLOR, SEVERITY_LABEL } from "@/lib/constants";
import type { Anomaly, ReconciliationSummary, Severity } from "@/lib/types";
import { EmptyState } from "@/components/ui";

const box = "h-64 w-full";

export function MatchStatusChart({ summary }: { summary: ReconciliationSummary }) {
  const data = (["MATCHED", "LIKELY_MATCH", "REVIEW_REQUIRED", "UNMATCHED"] as const)
    .map((k) => ({ key: k, name: MATCH_LABEL[k], value: { MATCHED: summary.matched, LIKELY_MATCH: summary.likely_matches, REVIEW_REQUIRED: summary.review_required, UNMATCHED: summary.unmatched }[k] ?? 0 }))
    .filter((d) => d.value > 0);
  if (!data.length) return <EmptyState title="No transactions to chart." />;
  return (
    <div className={box} role="img" aria-label={`Match status: ${data.map((d) => `${d.name} ${d.value}`).join(", ")}`}>
      <ResponsiveContainer>
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" innerRadius={50} outerRadius={80} paddingAngle={2}>
            {data.map((d) => <Cell key={d.key} fill={MATCH_COLOR[d.key]} />)}
          </Pie>
          <Tooltip /><Legend verticalAlign="bottom" iconType="circle" />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

export function AnomalyChart({ summary }: { summary: ReconciliationSummary }) {
  const data = ANOMALY_TYPES.map((t) => ({ type: t, name: ANOMALY_SHORT[t], value: summary.anomaly_counts?.[t] ?? 0 }));
  if (!data.some((d) => d.value > 0)) return <EmptyState title="No anomalies detected." />;
  return (
    <div className={box} role="img" aria-label={`Anomalies: ${data.map((d) => `${d.name} ${d.value}`).join(", ")}`}>
      <ResponsiveContainer>
        <BarChart data={data} margin={{ left: -20, right: 8, top: 8 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
          <XAxis dataKey="name" tick={{ fontSize: 11 }} interval={0} angle={-20} textAnchor="end" height={50} />
          <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
          <Tooltip cursor={{ fill: "#f1f5f9" }} />
          <Bar dataKey="value" name="Anomalies" radius={[4, 4, 0, 0]}>{data.map((d) => <Cell key={d.type} fill={ANOMALY_COLOR[d.type]} />)}</Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function RiskChart({ anomalies }: { anomalies: Anomaly[] }) {
  const sev: Severity[] = ["LOW", "MEDIUM", "HIGH"];
  const data = sev.map((s) => ({ sev: s, name: SEVERITY_LABEL[s], value: anomalies.filter((a) => a.severity === s).length }));
  if (!data.some((d) => d.value > 0)) return <EmptyState title="No anomalies detected." />;
  return (
    <div className={box} role="img" aria-label={`Risk: ${data.map((d) => `${d.name} ${d.value}`).join(", ")}`}>
      <ResponsiveContainer>
        <BarChart data={data} margin={{ left: -20, right: 8, top: 8 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
          <XAxis dataKey="name" tick={{ fontSize: 12 }} /><YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
          <Tooltip cursor={{ fill: "#f1f5f9" }} />
          <Bar dataKey="value" name="Anomalies" radius={[4, 4, 0, 0]}>{data.map((d) => <Cell key={d.sev} fill={SEVERITY_COLOR[d.sev]} />)}</Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
