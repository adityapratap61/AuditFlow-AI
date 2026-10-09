"use client";
import { useEffect, useState } from "react";
import { api, ApiError, errorMessage, fetchAll } from "@/lib/api";
import type { Anomaly } from "@/lib/types";

export function useAnomalies(runId: string | null) {
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [loading, setLoading] = useState(!!runId);
  const [error, setError] = useState<string | null>(null);
  const [network, setNetwork] = useState(false);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!runId) { setAnomalies([]); setLoading(false); return; }
    let cancelled = false;
    setLoading(true); setError(null); setNetwork(false);
    fetchAll((limit, offset) => api.anomalies({ run_id: runId, limit, offset }))
      .then((a) => { if (!cancelled) setAnomalies(a); })
      .catch((e) => { if (!cancelled) { setError(errorMessage(e, "Unable to load anomalies.")); setNetwork(e instanceof ApiError && e.isNetwork); } })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [runId, tick]);

  return { anomalies, loading, error, network, reload: () => setTick((t) => t + 1) };
}
