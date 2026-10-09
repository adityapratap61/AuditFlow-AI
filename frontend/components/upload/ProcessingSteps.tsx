"use client";
import { CheckCircle2, Circle, Loader2, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Stage } from "@/hooks/useReconciliation";
import type { UploadResult } from "@/lib/types";

type S = "done" | "active" | "pending" | "failed";

/** Steps mirror the real requests: two uploads, then one synchronous /api/reconcile call. */
export function ProcessingSteps({ stage, failedAt, bank, accounting }: { stage: Stage; failedAt: Stage | null; bank: UploadResult | null; accounting: UploadResult | null }) {
  const st = (key: Stage, idx: number): S => {
    const order: Stage[] = ["uploading-bank", "uploading-accounting", "reconciling", "done"];
    if (stage === "error") {
      const f = order.indexOf(failedAt ?? "uploading-bank");
      return idx < f ? "done" : idx === f ? "failed" : "pending";
    }
    const cur = order.indexOf(stage);
    return idx < cur || stage === "done" ? "done" : idx === cur ? "active" : "pending";
  };
  const steps: { label: string; detail?: string; s: S }[] = [
    { label: "Uploading bank statement", detail: bank ? `${bank.transactions_extracted} transactions parsed` : undefined, s: st("uploading-bank", 0) },
    { label: "Uploading accounting data", detail: accounting ? `${accounting.transactions_extracted} transactions parsed` : undefined, s: st("uploading-accounting", 1) },
    { label: "Matching transactions, detecting anomalies & investigating discrepancies", detail: "Running on the backend — this can take a little while for large files", s: st("reconciling", 2) },
  ];
  return (
    <ol className="space-y-3" aria-live="polite">
      {steps.map((x) => (
        <li key={x.label} className="flex items-start gap-3">
          {x.s === "done" ? <CheckCircle2 className="mt-0.5 h-5 w-5 text-emerald-600" aria-label="Completed" />
            : x.s === "active" ? <Loader2 className="mt-0.5 h-5 w-5 animate-spin text-brand-600" aria-label="In progress" />
            : x.s === "failed" ? <XCircle className="mt-0.5 h-5 w-5 text-red-600" aria-label="Failed" />
            : <Circle className="mt-0.5 h-5 w-5 text-slate-300" aria-label="Pending" />}
          <div>
            <p className={cn("text-sm font-medium", x.s === "pending" ? "text-slate-400" : "text-navy-900")}>{x.label}</p>
            {x.detail && x.s !== "pending" && <p className="text-xs text-slate-500">{x.detail}</p>}
          </div>
        </li>
      ))}
    </ol>
  );
}
