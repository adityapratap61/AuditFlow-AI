"use client";
import { useCallback, useState } from "react";
import { api, errorMessage } from "@/lib/api";
import type { ReconciliationResult, UploadResult } from "@/lib/types";

export type Stage = "idle" | "uploading-bank" | "uploading-accounting" | "reconciling" | "done" | "error";

/** Upload both files into one run, then run the (synchronous) reconciliation. Stages reflect real request progress. */
export function useReconciliation() {
  const [stage, setStage] = useState<Stage>("idle");
  const [bank, setBank] = useState<UploadResult | null>(null);
  const [accounting, setAccounting] = useState<UploadResult | null>(null);
  const [result, setResult] = useState<ReconciliationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [failedAt, setFailedAt] = useState<Stage | null>(null);

  const reset = useCallback(() => { setStage("idle"); setBank(null); setAccounting(null); setResult(null); setError(null); setFailedAt(null); }, []);

  const start = useCallback(async (bankFile: File, accFile: File): Promise<ReconciliationResult | null> => {
    setError(null); setFailedAt(null); setBank(null); setAccounting(null); setResult(null);
    let current: Stage = "uploading-bank";
    try {
      setStage(current);
      const b = await api.uploadBank(bankFile); setBank(b);
      current = "uploading-accounting"; setStage(current);
      const a = await api.uploadAccounting(accFile, b.run_id); setAccounting(a);
      current = "reconciling"; setStage(current);
      let r: ReconciliationResult;
      try { r = await api.reconcile(b.run_id, true); }
      catch (e) {
        const msg = errorMessage(e, "");
        throw new Error(msg && !/unexpected/i.test(msg) ? msg : "Reconciliation could not be completed. Please check the uploaded files.");
      }
      setResult(r); setStage("done");
      return r;
    } catch (e) {
      setFailedAt(current); setStage("error");
      setError(e instanceof Error ? e.message : "Reconciliation could not be completed. Please check the uploaded files.");
      return null;
    }
  }, []);

  return { stage, bank, accounting, result, error, failedAt, start, reset };
}
