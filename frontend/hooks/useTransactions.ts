"use client";
import { useEffect, useState } from "react";
import { api, ApiError, errorMessage, fetchAll } from "@/lib/api";
import type { Match, Transaction } from "@/lib/types";

export interface TxnData { transactions: Transaction[]; matches: Match[] }
const cache = new Map<string, TxnData>();

/** Loads all transactions + matches for a run once (cached per run) so filtering/search can be done client-side. */
export function useTransactions(runId: string | null) {
  const [data, setData] = useState<TxnData | null>(runId ? cache.get(runId) ?? null : null);
  const [loading, setLoading] = useState(!!runId && !cache.has(runId));
  const [error, setError] = useState<string | null>(null);
  const [network, setNetwork] = useState(false);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!runId) { setData(null); setLoading(false); return; }
    if (tick === 0 && cache.has(runId)) { setData(cache.get(runId)!); setLoading(false); return; }
    let cancelled = false;
    setLoading(true); setError(null); setNetwork(false);
    Promise.all([
      fetchAll((limit, offset) => api.transactions({ run_id: runId, limit, offset })),
      fetchAll((limit, offset) => api.matches({ run_id: runId, limit, offset })),
    ]).then(([transactions, matches]) => {
      if (cancelled) return;
      const d = { transactions, matches }; cache.set(runId, d); setData(d);
    }).catch((e) => {
      if (cancelled) return;
      setError(errorMessage(e, "Unable to load transactions.")); setNetwork(e instanceof ApiError && e.isNetwork);
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [runId, tick]);

  return { data, loading, error, network, reload: () => { if (runId) cache.delete(runId); setTick((t) => t + 1); } };
}
export function clearTransactionCache(): void { cache.clear(); }
