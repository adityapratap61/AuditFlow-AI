"use client";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight, Eye, Search, X } from "lucide-react";
import { AnomalyBadge, Button, EmptyState, MatchBadge, RiskBadge, Badge } from "@/components/ui";
import { ANOMALY_LABEL, ANOMALY_TYPES } from "@/lib/constants";
import type { Anomaly, AnomalyType, Match, Transaction } from "@/lib/types";
import { cn, formatDate, formatMoney, pct, riskFor, type RiskLevel } from "@/lib/utils";

const PAGE = 25;
type StatusFilter = "ALL" | "MATCHED" | "LIKELY_MATCH" | "REVIEW_REQUIRED" | "UNMATCHED" | "HIGH_RISK";
type SortKey = "date" | "amount";

interface Row { t: Transaction; match: Match | null; counterpart: Transaction | null; anomalies: Anomaly[]; risk: RiskLevel }

const STATUS_OPTS: { v: StatusFilter; l: string }[] = [
  { v: "ALL", l: "All" }, { v: "MATCHED", l: "Matched" }, { v: "LIKELY_MATCH", l: "Likely Match" },
  { v: "REVIEW_REQUIRED", l: "Review Required" }, { v: "UNMATCHED", l: "Unmatched" }, { v: "HIGH_RISK", l: "High Risk" },
];

export function TransactionTable({ transactions, matches, anomalies }: { transactions: Transaction[]; matches: Match[]; anomalies: Anomaly[] }) {
  const [source, setSource] = useState<"BANK" | "ACCOUNTING">("BANK");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<StatusFilter>("ALL");
  const [atype, setAtype] = useState<AnomalyType | "ALL">("ALL");
  const [from, setFrom] = useState(""); const [to, setTo] = useState("");
  const [sort, setSort] = useState<{ key: SortKey; dir: "asc" | "desc" }>({ key: "date", dir: "asc" });
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<Row | null>(null);

  const rows = useMemo<Row[]>(() => {
    const byId = new Map(transactions.map((t) => [t.id, t]));
    const matchOf = new Map<string, Match>();
    for (const m of matches) { matchOf.set(m.bank_transaction_id, m); if (m.accounting_transaction_id) matchOf.set(m.accounting_transaction_id, m); }
    const anomOf = new Map<string, Anomaly[]>();
    const add = (id: string | null, a: Anomaly) => { if (!id) return; const l = anomOf.get(id); l ? l.push(a) : anomOf.set(id, [a]); };
    for (const a of anomalies) { add(a.transaction_id, a); if (a.related_transaction_id !== a.transaction_id) add(a.related_transaction_id, a); }
    return transactions.filter((t) => t.source === source).map((t) => {
      const m = matchOf.get(t.id) ?? null;
      const cpId = t.matched_transaction_id ?? (m ? (t.source === "BANK" ? m.accounting_transaction_id : m.bank_transaction_id) : null);
      const an = anomOf.get(t.id) ?? [];
      return { t, match: m, counterpart: cpId ? byId.get(cpId) ?? null : null, anomalies: an, risk: riskFor(t, an) };
    });
  }, [transactions, matches, anomalies, source]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    const list = rows.filter(({ t, anomalies: an, risk }) => {
      if (q && !`${t.description} ${t.raw_description} ${t.reference ?? ""}`.toLowerCase().includes(q)) return false;
      if (status === "HIGH_RISK" ? risk !== "High" : status !== "ALL" && t.match_status !== status) return false;
      if (atype !== "ALL" && !an.some((a) => a.anomaly_type === atype)) return false;
      if (from && t.date < from) return false;
      if (to && t.date > to) return false;
      return true;
    });
    const k = sort.key, d = sort.dir === "asc" ? 1 : -1;
    return [...list].sort((a, b) => (k === "amount" ? a.t.amount - b.t.amount : a.t.date.localeCompare(b.t.date)) * d);
  }, [rows, search, status, atype, from, to, sort]);

  useEffect(() => setPage(0), [search, status, atype, from, to, sort, source]);
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE));
  const view = filtered.slice(page * PAGE, page * PAGE + PAGE);
  const toggle = (key: SortKey) => setSort((s) => (s.key === key ? { key, dir: s.dir === "asc" ? "desc" : "asc" } : { key, dir: "desc" }));
  const hasFilters = !!(search || status !== "ALL" || atype !== "ALL" || from || to);
  const clear = () => { setSearch(""); setStatus("ALL"); setAtype("ALL"); setFrom(""); setTo(""); };

  const SortIcon = ({ k }: { k: SortKey }) => sort.key !== k ? <ArrowUpDown className="h-3 w-3" aria-hidden /> : sort.dir === "asc" ? <ArrowUp className="h-3 w-3" aria-hidden /> : <ArrowDown className="h-3 w-3" aria-hidden />;
  const input = "rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 placeholder:text-slate-400";

  return (
    <div>
      <div className="space-y-3 border-b border-slate-100 p-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative min-w-[14rem] flex-1">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" aria-hidden />
            <input type="search" aria-label="Search by description, vendor or reference" placeholder="Search description, vendor or reference…" value={search} onChange={(e) => setSearch(e.target.value)} className={cn(input, "w-full pl-9")} />
          </div>
          <div role="group" aria-label="Source" className="inline-flex rounded-lg border border-slate-300 bg-white p-0.5">
            {(["BANK", "ACCOUNTING"] as const).map((s) => (
              <button key={s} onClick={() => setSource(s)} aria-pressed={source === s} className={cn("rounded-md px-3 py-1.5 text-sm font-medium", source === s ? "bg-navy-900 text-white" : "text-slate-600 hover:bg-slate-100")}>{s === "BANK" ? "Bank" : "Accounting"}</button>
            ))}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Status filter">
          {STATUS_OPTS.map((o) => (
            <button key={o.v} onClick={() => setStatus(o.v)} aria-pressed={status === o.v}
              className={cn("rounded-full border px-3 py-1 text-xs font-medium transition", status === o.v ? "border-brand-600 bg-brand-600 text-white" : "border-slate-300 bg-white text-slate-600 hover:bg-slate-50")}>{o.l}</button>
          ))}
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-xs text-slate-500">Anomaly
            <select value={atype} onChange={(e) => setAtype(e.target.value as AnomalyType | "ALL")} className={cn(input, "mt-1 block")}>
              <option value="ALL">All anomalies</option>{ANOMALY_TYPES.map((a) => <option key={a} value={a}>{ANOMALY_LABEL[a]}</option>)}
            </select></label>
          <label className="text-xs text-slate-500">From<input type="date" value={from} onChange={(e) => setFrom(e.target.value)} className={cn(input, "mt-1 block")} /></label>
          <label className="text-xs text-slate-500">To<input type="date" value={to} onChange={(e) => setTo(e.target.value)} className={cn(input, "mt-1 block")} /></label>
          {hasFilters && <Button variant="ghost" onClick={clear}><X className="h-4 w-4" aria-hidden />Clear filters</Button>}
          <p className="ml-auto text-xs text-slate-500" aria-live="polite">{filtered.length} of {rows.length} transactions</p>
        </div>
      </div>

      {rows.length === 0 ? <EmptyState title="No transactions found for this run." />
        : filtered.length === 0 ? <EmptyState title="No transactions match your filters." action={<Button variant="secondary" onClick={clear}>Clear filters</Button>} />
        : (
          <div className="table-wrap">
            <table className="w-full min-w-[60rem] text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th scope="col" className="px-4 py-3"><button className="inline-flex items-center gap-1 font-semibold uppercase" onClick={() => toggle("date")}>Date <SortIcon k="date" /></button></th>
                  <th scope="col" className="px-4 py-3">Description</th>
                  <th scope="col" className="px-4 py-3 text-right"><button className="inline-flex items-center gap-1 font-semibold uppercase" onClick={() => toggle("amount")}>Amount <SortIcon k="amount" /></button></th>
                  <th scope="col" className="px-4 py-3">Type</th><th scope="col" className="px-4 py-3">Status</th>
                  <th scope="col" className="px-4 py-3">{source === "BANK" ? "Accounting" : "Bank"} Match</th>
                  <th scope="col" className="px-4 py-3 text-right">Score</th><th scope="col" className="px-4 py-3">Anomaly</th>
                  <th scope="col" className="px-4 py-3">Risk</th><th scope="col" className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {view.map((r) => {
                  const top = r.anomalies[0];
                  return (
                    <tr key={r.t.id} className="hover:bg-slate-50/70">
                      <td className="whitespace-nowrap px-4 py-3 text-slate-600">{formatDate(r.t.date)}</td>
                      <td className="max-w-[16rem] px-4 py-3"><p className="truncate font-medium text-navy-900" title={r.t.raw_description}>{r.t.description}</p>{r.t.reference && <p className="truncate font-mono text-xs text-slate-400">{r.t.reference}</p>}</td>
                      <td className="whitespace-nowrap px-4 py-3 text-right font-medium tabular-nums">{formatMoney(r.t.amount, r.t.currency)}</td>
                      <td className="px-4 py-3"><Badge tone={r.t.transaction_type === "CREDIT" ? "teal" : "slate"}>{r.t.transaction_type === "CREDIT" ? "Credit" : "Debit"}</Badge></td>
                      <td className="px-4 py-3"><MatchBadge status={r.t.match_status} /></td>
                      <td className="max-w-[13rem] px-4 py-3 text-slate-600"><span className="block truncate" title={r.counterpart?.raw_description}>{r.counterpart?.description ?? "—"}</span></td>
                      <td className="px-4 py-3 text-right tabular-nums">{r.match ? pct(r.match.score, false) : "—"}</td>
                      <td className="px-4 py-3">{top ? <AnomalyBadge type={top.anomaly_type} /> : <span className="text-slate-400">—</span>}</td>
                      <td className="px-4 py-3"><RiskBadge risk={r.risk} /></td>
                      <td className="whitespace-nowrap px-4 py-3 text-right">
                        <button onClick={() => setSelected(r)} className="mr-1 inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100"><Eye className="h-3.5 w-3.5" aria-hidden />View</button>
                        {top ? <Link href={`/anomalies/${top.id}?investigate=1`} className="rounded-md bg-brand-50 px-2 py-1 text-xs font-medium text-brand-700 hover:bg-brand-100">Investigate</Link>
                          : <span className="rounded-md px-2 py-1 text-xs text-slate-300" title="No anomaly to investigate">Investigate</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

      {filtered.length > PAGE && (
        <div className="flex items-center justify-between border-t border-slate-100 px-4 py-3 text-sm text-slate-600">
          <span>Page {page + 1} of {pages}</span>
          <div className="flex gap-2">
            <Button variant="secondary" disabled={page === 0} onClick={() => setPage((p) => p - 1)} aria-label="Previous page"><ChevronLeft className="h-4 w-4" /></Button>
            <Button variant="secondary" disabled={page >= pages - 1} onClick={() => setPage((p) => p + 1)} aria-label="Next page"><ChevronRight className="h-4 w-4" /></Button>
          </div>
        </div>
      )}
      {selected && <TransactionDrawer row={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}

function Field({ k, v }: { k: string; v: React.ReactNode }) {
  return <div className="flex justify-between gap-4 py-1.5 text-sm"><dt className="text-slate-500">{k}</dt><dd className="text-right font-medium text-navy-900">{v}</dd></div>;
}
function TxnBlock({ title, t }: { title: string; t: Transaction | null }) {
  return (
    <div className="rounded-lg border border-slate-200 p-4">
      <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</h3>
      {!t ? <p className="text-sm text-slate-500">No record available.</p> : (
        <dl className="divide-y divide-slate-100">
          <Field k="Date" v={formatDate(t.date)} /><Field k="Description" v={t.raw_description} />
          <Field k="Amount" v={formatMoney(t.amount, t.currency)} /><Field k="Type" v={t.transaction_type} />
          <Field k="Reference" v={t.reference ?? "—"} />
        </dl>
      )}
    </div>
  );
}
function TransactionDrawer({ row, onClose }: { row: Row; onClose: () => void }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", h); return () => window.removeEventListener("keydown", h);
  }, [onClose]);
  const m = row.match;
  return (
    <div className="fixed inset-0 z-40 flex justify-end" role="dialog" aria-modal="true" aria-label="Transaction details">
      <div className="absolute inset-0 bg-slate-900/40" onClick={onClose} />
      <div className="relative h-full w-full max-w-lg overflow-y-auto bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between"><h2 className="text-lg font-semibold text-navy-900">Transaction details</h2><button aria-label="Close" onClick={onClose} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100"><X className="h-5 w-5" /></button></div>
        <div className="mb-4 flex flex-wrap gap-2"><MatchBadge status={row.t.match_status} /><RiskBadge risk={row.risk} /></div>
        <div className="space-y-4">
          <TxnBlock title={row.t.source === "BANK" ? "Bank record" : "Accounting record"} t={row.t} />
          <TxnBlock title={row.t.source === "BANK" ? "Accounting record" : "Bank record"} t={row.counterpart} />
          {m && (
            <div className="rounded-lg border border-slate-200 p-4">
              <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Match evidence</h3>
              <dl className="divide-y divide-slate-100">
                <Field k="Match score" v={pct(m.score, false)} />
                {m.date_diff_days != null && <Field k="Date difference" v={`${m.date_diff_days} day(s)`} />}
                {m.description_similarity != null && <Field k="Description similarity" v={pct(m.description_similarity, false)} />}
                {m.amount_difference != null && <Field k="Amount difference" v={formatMoney(m.amount_difference)} />}
              </dl>
              {m.reasons && m.reasons.length > 0 && <ul className="mt-2 list-disc space-y-0.5 pl-5 text-sm text-slate-600">{m.reasons.map((r) => <li key={r}>{r}</li>)}</ul>}
            </div>
          )}
          {row.anomalies.length > 0 && (
            <div className="rounded-lg border border-slate-200 p-4">
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Anomalies</h3>
              <ul className="space-y-2">{row.anomalies.map((a) => (
                <li key={a.id} className="flex items-center justify-between gap-2"><AnomalyBadge type={a.anomaly_type} /><Link className="text-sm font-medium text-brand-600 hover:underline" href={`/anomalies/${a.id}`}>Open</Link></li>
              ))}</ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
