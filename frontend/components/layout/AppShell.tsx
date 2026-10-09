"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { AlertTriangle, FileText, LayoutDashboard, List, Menu, Search, UploadCloud, X } from "lucide-react";
import { Logo } from "@/components/ui";
import { NAV } from "@/lib/constants";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { useRun } from "@/hooks/useRun";

const ICONS = { layout: LayoutDashboard, upload: UploadCloud, list: List, alert: AlertTriangle, search: Search, file: FileText };

function Nav({ onNavigate }: { onNavigate?: () => void }) {
  const path = usePathname();
  return (
    <nav aria-label="Primary" className="flex flex-col gap-1">
      {NAV.map((n) => {
        const Icon = ICONS[n.icon];
        const active = path === n.href || path.startsWith(`${n.href}/`);
        return (
          <Link key={n.href} href={n.href} onClick={onNavigate} aria-current={active ? "page" : undefined}
            className={cn("flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition",
              active ? "bg-white/10 text-white" : "text-slate-300 hover:bg-white/5 hover:text-white")}>
            <Icon className="h-4 w-4" aria-hidden />{n.label}
          </Link>
        );
      })}
    </nav>
  );
}

function BackendStatus() {
  const [state, setState] = useState<{ ok: boolean; ollama: string } | null>(null);
  useEffect(() => {
    let alive = true;
    api.health().then((h) => alive && setState({ ok: h.status === "healthy", ollama: h.ollama })).catch(() => alive && setState({ ok: false, ollama: "unavailable" }));
    return () => { alive = false; };
  }, []);
  if (!state) return null;
  return (
    <div className="rounded-lg bg-white/5 p-3 text-xs text-slate-300">
      <p className="flex items-center gap-2"><span className={cn("h-2 w-2 rounded-full", state.ok ? "bg-emerald-400" : "bg-red-400")} />{state.ok ? "Backend connected" : "Backend offline"}</p>
      {state.ok && <p className="mt-1 text-slate-400">AI model: {state.ollama === "available" ? "Ollama active" : "deterministic fallback"}</p>}
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const path = usePathname();
  const [open, setOpen] = useState(false);
  const { run } = useRun();
  useEffect(() => setOpen(false), [path]);
  if (path === "/") return <>{children}</>;

  return (
    <div className="min-h-screen lg:pl-64">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col gap-6 bg-navy-950 p-4 lg:flex">
        <Link href="/" aria-label="AuditFlow AI home" className="px-2 pt-1"><Logo light /></Link>
        <Nav />
        <div className="mt-auto"><BackendStatus /></div>
      </aside>

      <header className="sticky top-0 z-20 flex items-center justify-between border-b border-slate-200 bg-white/90 px-4 py-3 backdrop-blur sm:px-6">
        <div className="flex items-center gap-3">
          <button className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 lg:hidden" aria-label="Open navigation" aria-expanded={open} onClick={() => setOpen(true)}><Menu className="h-5 w-5" /></button>
          <div className="lg:hidden"><Logo /></div>
          <p className="hidden text-sm text-slate-500 lg:block">AI-Powered Financial Reconciliation &amp; Anomaly Investigation</p>
        </div>
        {run?.run_id && <p className="hidden text-xs text-slate-500 sm:block">Run <span className="font-mono text-slate-700">{run.run_id.slice(0, 8)}</span>{run.bank_filename ? ` · ${run.bank_filename}` : ""}</p>}
      </header>

      {open && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <div className="absolute inset-0 bg-slate-900/50" onClick={() => setOpen(false)} />
          <div className="absolute inset-y-0 left-0 flex w-72 flex-col gap-6 bg-navy-950 p-4">
            <div className="flex items-center justify-between px-2"><Logo light /><button aria-label="Close navigation" className="text-slate-300" onClick={() => setOpen(false)}><X className="h-5 w-5" /></button></div>
            <Nav onNavigate={() => setOpen(false)} />
            <div className="mt-auto"><BackendStatus /></div>
          </div>
        </div>
      )}
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:py-8">{children}</main>
    </div>
  );
}
