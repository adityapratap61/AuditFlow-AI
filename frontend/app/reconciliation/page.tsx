"use client";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowRight, Database, RotateCcw } from "lucide-react";
import { Button, Card, CardHeader, ErrorState, LinkButton, PageHeader, Spinner } from "@/components/ui";
import { FileDropzone, type UploadState } from "@/components/upload/FileDropzone";
import { ProcessingSteps } from "@/components/upload/ProcessingSteps";
import { SummaryView } from "@/components/dashboard/SummaryView";
import { useReconciliation } from "@/hooks/useReconciliation";
import { useRun } from "@/hooks/useRun";
import { useToast } from "@/components/ui/Toast";
import { clearTransactionCache } from "@/hooks/useTransactions";
import { ACCEPT } from "@/lib/constants";

const SAMPLES = { bank: "/sample/bank_statement.pdf", accounting: "/sample/accounting_export.csv" };

async function loadSample(path: string, type: string): Promise<File> {
  const res = await fetch(path);
  if (!res.ok) throw new Error("Sample file not found.");
  return new File([await res.blob()], path.split("/").pop()!, { type });
}

function Flow() {
  const params = useSearchParams();
  const toast = useToast();
  const { setRunId } = useRun();
  const rec = useReconciliation();
  const [bank, setBank] = useState<File | null>(null);
  const [acc, setAcc] = useState<File | null>(null);
  const [loadingSample, setLoadingSample] = useState(false);
  const demoLoaded = useRef(false);

  const busy = rec.stage === "uploading-bank" || rec.stage === "uploading-accounting" || rec.stage === "reconciling";

  const loadSamples = useCallback(async () => {
    setLoadingSample(true);
    try {
      const [b, a] = await Promise.all([loadSample(SAMPLES.bank, "application/pdf"), loadSample(SAMPLES.accounting, "text/csv")]);
      setBank(b); setAcc(a); rec.reset();
      toast.info("Sample files loaded. They will be processed by the real backend.");
    } catch { toast.error("Could not load the sample files."); }
    finally { setLoadingSample(false); }
  }, [rec, toast]);

  useEffect(() => {
    if (params.get("demo") === "1" && !demoLoaded.current) { demoLoaded.current = true; void loadSamples(); }
  }, [params, loadSamples]);

  const start = async () => {
    if (!bank || !acc) return;
    toast.info("Files uploading…");
    const r = await rec.start(bank, acc);
    if (r) {
      setRunId(r.run_id); clearTransactionCache();
      toast.success("Reconciliation complete.");
    } else toast.error("Reconciliation could not be completed.");
  };
  const reset = () => { rec.reset(); setBank(null); setAcc(null); };

  const bankState: UploadState = rec.stage === "uploading-bank" ? "uploading" : rec.bank ? "uploaded" : rec.failedAt === "uploading-bank" ? "failed" : "selected";
  const accState: UploadState = rec.stage === "uploading-accounting" ? "uploading" : rec.accounting ? "uploaded" : rec.failedAt === "uploading-accounting" ? "failed" : "selected";

  if (rec.stage === "done" && rec.result) {
    return (
      <div className="space-y-6">
        <Card className="flex flex-wrap items-center justify-between gap-3 border-emerald-200 bg-emerald-50/50 p-5">
          <div><p className="text-sm font-semibold text-emerald-800">Reconciliation complete</p><p className="text-xs text-emerald-700">{rec.result.bank_filename} ↔ {rec.result.accounting_filename}</p></div>
          <div className="flex flex-wrap gap-2">
            <LinkButton href="/anomalies" variant="secondary">View Anomalies</LinkButton>
            <LinkButton href="/transactions" variant="secondary">View Transactions</LinkButton>
            <LinkButton href="/dashboard">Open Dashboard <ArrowRight className="h-4 w-4" aria-hidden /></LinkButton>
          </div>
        </Card>
        <SummaryView run={rec.result} anomalies={rec.result.anomalies} />
        <Button variant="ghost" onClick={reset}><RotateCcw className="h-4 w-4" aria-hidden />Run another reconciliation</Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-6 md:grid-cols-2">
        <FileDropzone label="Bank Statement" hint="PDF or CSV · max 20 MB" exts={ACCEPT.bank.exts} invalidMessage={ACCEPT.bank.error}
          file={bank} state={bankState} stateText={rec.bank ? `Uploaded · ${rec.bank.transactions_extracted} transactions` : undefined}
          onSelect={(f) => { setBank(f); rec.reset(); }} disabled={busy} />
        <FileDropzone label="Accounting Export" hint="CSV · max 20 MB" exts={ACCEPT.accounting.exts} invalidMessage={ACCEPT.accounting.error}
          file={acc} state={accState} stateText={rec.accounting ? `Uploaded · ${rec.accounting.transactions_extracted} transactions` : undefined}
          onSelect={(f) => { setAcc(f); rec.reset(); }} disabled={busy} />
      </div>

      {[...(rec.bank?.warnings ?? []), ...(rec.accounting?.warnings ?? [])].map((w, i) => <p key={i} className="rounded-lg bg-amber-50 px-4 py-2 text-sm text-amber-800">{w}</p>)}

      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={start} disabled={!bank || !acc || busy} loading={busy} className="px-6 py-2.5">{busy ? "Processing…" : "Start Reconciliation"}</Button>
        <Button variant="secondary" onClick={loadSamples} disabled={busy || loadingSample} loading={loadingSample}><Database className="h-4 w-4" aria-hidden />Load Sample Data</Button>
        {!bank || !acc ? <span className="text-xs text-slate-500">Select both files to continue.</span> : null}
      </div>

      {rec.stage !== "idle" && (
        <Card>
          <CardHeader title={rec.stage === "error" ? "Reconciliation failed" : "Processing"} />
          <div className="space-y-4 p-5">
            <ProcessingSteps stage={rec.stage} failedAt={rec.failedAt} bank={rec.bank} accounting={rec.accounting} />
            {rec.stage === "error" && rec.error && <ErrorState message={rec.error} onRetry={start} />}
          </div>
        </Card>
      )}
    </div>
  );
}

export default function ReconciliationPage() {
  return (
    <>
      <PageHeader title="Reconciliation" subtitle="Upload a bank statement and an accounting export to reconcile them" />
      <Suspense fallback={<Spinner />}><Flow /></Suspense>
      <p className="mt-8 text-xs text-slate-500">Previous results are available on the <Link href="/dashboard" className="text-brand-600 underline">dashboard</Link>.</p>
    </>
  );
}
