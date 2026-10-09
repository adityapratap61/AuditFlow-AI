"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { Card, ErrorState, LinkButton, PageHeader, Spinner } from "@/components/ui";
import { InvestigationPanel } from "@/components/investigation/InvestigationPanel";
import { api, ApiError, errorMessage } from "@/lib/api";
import type { Investigation, Transaction } from "@/lib/types";

export default function InvestigationPage() {
  const { id } = useParams<{ id: string }>();
  const [inv, setInv] = useState<Investigation | null>(null);
  const [tx, setTx] = useState<Transaction | null>(null);
  const [err, setErr] = useState<{ m: string; n: boolean } | null>(null);
  const load = useCallback(async () => {
    setErr(null); setInv(null);
    try {
      const i = await api.investigation(id); setInv(i);
      try { setTx(await api.transaction(i.transaction_id)); } catch { /* optional */ }
    } catch (e) { setErr({ m: errorMessage(e, "Unable to load this investigation."), n: e instanceof ApiError && e.isNetwork }); }
  }, [id]);
  useEffect(() => { void load(); }, [load]);
  return (
    <div className="space-y-6">
      <Link href="/investigations" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-navy-900"><ArrowLeft className="h-4 w-4" aria-hidden />Back to investigations</Link>
      <PageHeader title="Investigation" subtitle={tx ? `${tx.description}` : undefined} action={inv?.anomaly_id ? <LinkButton href={`/anomalies/${inv.anomaly_id}`} variant="secondary">View anomaly</LinkButton> : undefined} />
      {err ? <ErrorState message={err.m} network={err.n} onRetry={load} /> : !inv ? <Card><Spinner label="Loading investigation…" /></Card> : <InvestigationPanel inv={inv} bank={tx} />}
    </div>
  );
}
