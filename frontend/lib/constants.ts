import type { AnomalyType, MatchStatus, Severity } from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");
export const RUN_STORAGE_KEY = "auditflow.runId";

export const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: "layout" },
  { href: "/reconciliation", label: "Reconciliation", icon: "upload" },
  { href: "/transactions", label: "Transactions", icon: "list" },
  { href: "/anomalies", label: "Anomalies", icon: "alert" },
  { href: "/investigations", label: "Investigations", icon: "search" },
  { href: "/reports", label: "Reports", icon: "file" },
] as const;

export const ANOMALY_LABEL: Record<AnomalyType, string> = {
  MISSING_TRANSACTION: "Missing Transaction",
  DUPLICATE_TRANSACTION: "Duplicate",
  TIMING_DIFFERENCE: "Timing Difference",
  AMOUNT_MISMATCH: "Amount Mismatch",
  HIGH_VALUE_MISMATCH: "High Value Mismatch",
  POTENTIALLY_SUSPICIOUS: "Potentially Suspicious",
};
export const ANOMALY_SHORT: Record<AnomalyType, string> = {
  MISSING_TRANSACTION: "Missing", DUPLICATE_TRANSACTION: "Duplicate", TIMING_DIFFERENCE: "Timing",
  AMOUNT_MISMATCH: "Amount", HIGH_VALUE_MISMATCH: "High Value", POTENTIALLY_SUSPICIOUS: "Suspicious",
};
export const ANOMALY_TYPES = Object.keys(ANOMALY_LABEL) as AnomalyType[];

export const MATCH_LABEL: Record<MatchStatus, string> = {
  MATCHED: "Matched", LIKELY_MATCH: "Likely Match", REVIEW_REQUIRED: "Review Required", UNMATCHED: "Unmatched",
};
export const SEVERITY_LABEL: Record<Severity, string> = { HIGH: "High", MEDIUM: "Medium", LOW: "Low" };

export const MATCH_COLOR: Record<MatchStatus, string> = {
  MATCHED: "#16a34a", LIKELY_MATCH: "#0d9488", REVIEW_REQUIRED: "#d97706", UNMATCHED: "#dc2626",
};
export const ANOMALY_COLOR: Record<AnomalyType, string> = {
  MISSING_TRANSACTION: "#dc2626", DUPLICATE_TRANSACTION: "#7c3aed", TIMING_DIFFERENCE: "#d97706",
  AMOUNT_MISMATCH: "#ea580c", HIGH_VALUE_MISMATCH: "#be123c", POTENTIALLY_SUSPICIOUS: "#475569",
};
export const SEVERITY_COLOR: Record<Severity, string> = { LOW: "#16a34a", MEDIUM: "#d97706", HIGH: "#dc2626" };

export const TOOL_LABEL: Record<string, string> = {
  search_by_amount: "Searching exact amount",
  search_by_reference: "Searching by reference",
  search_by_date_range: "Checking nearby dates",
  retry_with_relaxed_tolerance: "Applying relaxed tolerance",
  search_by_description: "Searching by description",
  fuzzy_search_transactions: "Comparing vendor names (fuzzy)",
  compare_transactions: "Comparing candidate transactions",
  check_duplicates: "Checking duplicates",
};

export const ACCEPT = {
  bank: { exts: [".pdf", ".csv"], error: "Please upload a PDF or CSV bank statement." },
  accounting: { exts: [".csv"], error: "Please upload a CSV accounting export." },
};
export const MAX_UPLOAD_MB = 20;
