"use client";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, ApiError, errorMessage } from "@/lib/api";
import { RUN_STORAGE_KEY } from "@/lib/constants";
import type { ReconciliationResult } from "@/lib/types";

interface RunCtx {
  runId: string | null; run: ReconciliationResult | null; loading: boolean; error: string | null; network: boolean;
  setRunId: (id: string | null) => void; refresh: () => Promise<void>;
}
const Ctx = createContext<RunCtx | null>(null);

/** Tracks the active reconciliation run (persisted in localStorage; falls back to the latest completed run). */
export function RunProvider({ children }: { children: ReactNode }) {
  const [runId, setRunIdState] = useState<string | null>(null);
  const [run, setRun] = useState<ReconciliationResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [network, setNetwork] = useState(false);
  const [bump, setBump] = useState(0);

  const setRunId = useCallback((id: string | null) => {
    try { id ? localStorage.setItem(RUN_STORAGE_KEY, id) : localStorage.removeItem(RUN_STORAGE_KEY); } catch { /* storage unavailable */ }
    setRunIdState(id);
    setBump((b) => b + 1);
  }, []);
  const refresh = useCallback(async () => { setBump((b) => b + 1); }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true); setError(null); setNetwork(false);
      try {
        let id = runId;
        if (!id) { try { id = localStorage.getItem(RUN_STORAGE_KEY); } catch { id = null; } }
        let result: ReconciliationResult | null = null;
        if (id) {
          try { result = await api.getRun(id); }
          catch (e) { if (e instanceof ApiError && e.code === "RUN_NOT_FOUND") id = null; else throw e; }
        }
        if (!result) {
          const list = await api.listRuns(20, 0);
          result = list.items.find((r) => r.status === "completed") ?? null;
          if (result) { try { localStorage.setItem(RUN_STORAGE_KEY, result.run_id); } catch { /* ignore */ } }
        }
        if (result && result.status === "completed" && (!result.summary || result.anomalies.length === 0)) {
          result = await api.getRun(result.run_id); // list omits anomaly arrays
        }
        if (!cancelled) { setRun(result); setRunIdState(result?.run_id ?? null); }
      } catch (e) {
        if (!cancelled) { setError(errorMessage(e, "Unable to load reconciliation data.")); setNetwork(e instanceof ApiError && e.isNetwork); setRun(null); }
      } finally { if (!cancelled) setLoading(false); }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bump]);

  const value = useMemo(() => ({ runId, run, loading, error, network, setRunId, refresh }), [runId, run, loading, error, network, setRunId, refresh]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
export function useRun(): RunCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error("useRun must be used inside RunProvider");
  return c;
}
