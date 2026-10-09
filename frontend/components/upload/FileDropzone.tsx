"use client";
import { useId, useRef, useState } from "react";
import { CheckCircle2, FileText, Loader2, UploadCloud, X, XCircle } from "lucide-react";
import { cn, fileExt, formatBytes } from "@/lib/utils";
import { MAX_UPLOAD_MB } from "@/lib/constants";

export type UploadState = "selected" | "uploading" | "uploaded" | "failed";

interface Props {
  label: string; hint: string; exts: string[]; invalidMessage: string;
  file: File | null; state?: UploadState; stateText?: string;
  onSelect: (f: File | null) => void; disabled?: boolean;
}

export function validateFile(f: File, exts: string[], invalidMessage: string): string | null {
  if (!exts.includes(fileExt(f.name))) return invalidMessage;
  if (f.size === 0) return "The selected file is empty.";
  if (f.size > MAX_UPLOAD_MB * 1024 * 1024) return `File exceeds the ${MAX_UPLOAD_MB} MB limit.`;
  return null;
}

export function FileDropzone({ label, hint, exts, invalidMessage, file, state = "selected", stateText, onSelect, disabled }: Props) {
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pick = (f: File | undefined | null) => {
    if (!f) return;
    const err = validateFile(f, exts, invalidMessage);
    setError(err);
    if (!err) onSelect(f);
  };

  return (
    <div>
      <p id={`${id}-l`} className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      {!file ? (
        <div role="button" tabIndex={disabled ? -1 : 0} aria-labelledby={`${id}-l`} aria-describedby={`${id}-h`} aria-disabled={disabled}
          onClick={() => !disabled && input.current?.click()}
          onKeyDown={(e) => { if ((e.key === "Enter" || e.key === " ") && !disabled) { e.preventDefault(); input.current?.click(); } }}
          onDragOver={(e) => { e.preventDefault(); if (!disabled) setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); if (!disabled) pick(e.dataTransfer.files?.[0]); }}
          className={cn("flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-4 py-10 text-center transition",
            drag ? "border-brand-500 bg-brand-50" : "border-slate-300 bg-white hover:border-brand-500 hover:bg-slate-50",
            error && "border-red-300", disabled && "cursor-not-allowed opacity-60")}>
          <UploadCloud className="mb-2 h-8 w-8 text-brand-600" aria-hidden />
          <p className="text-sm font-medium text-navy-900">Drag &amp; drop or <span className="text-brand-600 underline">browse</span></p>
          <p id={`${id}-h`} className="mt-1 text-xs text-slate-500">{hint}</p>
        </div>
      ) : (
        <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-card">
          <div className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-brand-50 text-brand-600"><FileText className="h-5 w-5" aria-hidden /></div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-navy-900" title={file.name}>{file.name}</p>
            <p className="text-xs text-slate-500">{fileExt(file.name).slice(1).toUpperCase()} · {formatBytes(file.size)}</p>
            <p className={cn("mt-1 flex items-center gap-1 text-xs font-medium",
              state === "uploaded" ? "text-emerald-600" : state === "failed" ? "text-red-600" : state === "uploading" ? "text-brand-600" : "text-slate-500")}>
              {state === "uploading" && <Loader2 className="h-3 w-3 animate-spin" aria-hidden />}
              {state === "uploaded" && <CheckCircle2 className="h-3 w-3" aria-hidden />}
              {state === "failed" && <XCircle className="h-3 w-3" aria-hidden />}
              {stateText ?? (state === "selected" ? "Ready to upload" : state)}
            </p>
          </div>
          <button type="button" aria-label={`Remove ${file.name}`} disabled={disabled} onClick={() => { setError(null); onSelect(null); if (input.current) input.current.value = ""; }}
            className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700 disabled:opacity-40"><X className="h-4 w-4" /></button>
        </div>
      )}
      <input ref={input} type="file" accept={exts.join(",")} className="sr-only" tabIndex={-1} aria-labelledby={`${id}-l`}
        onChange={(e) => { pick(e.target.files?.[0]); e.target.value = ""; }} />
      {error && <p role="alert" className="mt-2 text-sm text-red-600">{error}</p>}
    </div>
  );
}
