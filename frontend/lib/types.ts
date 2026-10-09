export type Source = "BANK" | "ACCOUNTING";
export type TxnType = "DEBIT" | "CREDIT";
export type MatchStatus = "MATCHED" | "LIKELY_MATCH" | "REVIEW_REQUIRED" | "UNMATCHED";
export type AnomalyType =
  | "MISSING_TRANSACTION" | "DUPLICATE_TRANSACTION" | "TIMING_DIFFERENCE"
  | "AMOUNT_MISMATCH" | "HIGH_VALUE_MISMATCH" | "POTENTIALLY_SUSPICIOUS";
export type Severity = "HIGH" | "MEDIUM" | "LOW";
export type RunStatus = "created" | "ready" | "processing" | "completed" | "failed";
export type OverallStatus = "RECONCILED" | "REVIEW_NEEDED" | "ATTENTION_REQUIRED";

export interface Page<T> { items: T[]; total: number; limit: number; offset: number }

export interface Transaction {
  id: string; run_id: string; source: Source; date: string; description: string; amount: number;
  transaction_type: TxnType; debit: number | null; credit: number | null; reference: string | null;
  balance: number | null; currency: string; raw_description: string; normalized_description: string;
  row_number: number | null; match_status: MatchStatus | null; matched_transaction_id: string | null;
}

export interface Match {
  id: string; run_id: string; bank_transaction_id: string; accounting_transaction_id: string | null;
  score: number; status: MatchStatus; level: number | null;
  signals: Record<string, number> | null; reasons: string[] | null;
  date_diff_days: number | null; description_similarity: number | null; amount_difference: number | null;
  matched_by: "ENGINE" | "AGENT"; bank_transaction: Transaction | null; accounting_transaction: Transaction | null;
}

export interface Anomaly {
  id: string; run_id: string; transaction_id: string; related_transaction_id: string | null;
  anomaly_type: AnomalyType; initial_type: AnomalyType | null; severity: Severity;
  status: "OPEN" | "INVESTIGATED"; source: Source; confidence: number | null; description: string;
  details: Record<string, unknown> | null; explanation: string | null;
  explanation_source: "ollama" | "fallback" | null; investigation_id: string | null; created_at: string;
}
export interface AnomalyDetail extends Anomaly { transaction: Transaction | null; related_transaction: Transaction | null }
export interface TransactionDetail extends Transaction { match: Match | null; anomalies: Anomaly[] }

export interface InvestigationStep {
  id: string; step_number: number; tool: string; arguments: Record<string, unknown> | null;
  result_summary: string; candidate_ids: string[] | null; decision: string | null; created_at: string;
}
export interface ExplanationDetail { evidence_points?: string[]; inference?: string; recommended_action?: string; [k: string]: unknown }
export interface Investigation {
  id: string; run_id: string; anomaly_id: string | null; transaction_id: string; status: string;
  conclusion: AnomalyType | null; confidence: number | null; explanation: string | null;
  explanation_source: "ollama" | "fallback" | null; explanation_detail: ExplanationDetail | null;
  evidence: { transaction?: Record<string, unknown>; counterpart?: Record<string, unknown>; comparison?: Record<string, unknown>; [k: string]: unknown } | null;
  counterpart_transaction_id: string | null; created_at: string; completed_at: string | null; steps: InvestigationStep[];
}

export interface ReconciliationSummary {
  total_bank_transactions: number; total_accounting_transactions: number; matched: number; likely_matches: number;
  review_required: number; unmatched: number; unmatched_accounting: number; match_rate: number;
  total_anomalies: number; high_risk: number; anomaly_counts: Partial<Record<AnomalyType, number>>;
  high_value_mismatches?: number; suspicious_transactions?: number; duplicate_groups?: number;
  duplicate_group_details?: { id: string; source: Source; transaction_ids: string[]; confidence: number; explanation: string }[];
  [k: string]: unknown;
}
export interface ReconciliationResult {
  run_id: string; status: RunStatus; overall_status: OverallStatus | null; summary: ReconciliationSummary | null;
  anomalies: Anomaly[]; processing_time: number | null; narrative: string | null;
  bank_filename: string | null; accounting_filename: string | null;
  created_at: string | null; completed_at: string | null; error: string | null;
}

export interface UploadResult {
  run_id: string; source: Source; filename: string; file_type: string; transactions_extracted: number;
  skipped_rows: number; parse_errors: { row?: number; error: string }[]; warnings: string[];
  run_status: RunStatus; bank_uploaded: boolean; accounting_uploaded: boolean; ready_to_reconcile: boolean;
}

export interface ReportTxn { id: string; source: Source; date: string; amount: number; transaction_type: TxnType; description: string; reference: string | null }
export interface ReportAnomalyRow {
  anomaly_id: string; type: AnomalyType; severity: Severity; description: string; confidence: number | null;
  transaction: ReportTxn | null; related_transaction: ReportTxn | null; explanation: string | null; disclaimer?: string;
}
export interface Report {
  report_metadata: { product: string; tagline: string; version: string; generated_at: string; run_id: string; bank_file: string | null; accounting_file: string | null; processing_time_seconds: number | null };
  overall_status: OverallStatus | null;
  totals: { bank_transactions: number; accounting_transactions: number; matched: number; likely_matches: number; review_required: number; unmatched: number; unmatched_accounting: number; match_rate: number };
  summary: Record<string, unknown>; narrative: string | null; narrative_source?: string | null;
  anomaly_counts: Partial<Record<AnomalyType, number>>; severity_counts: Record<Severity, number>;
  high_value_mismatches: ReportAnomalyRow[]; suspicious_transactions: ReportAnomalyRow[];
  duplicate_groups: unknown[];
  investigation_summaries: { investigation_id: string; anomaly_id: string | null; transaction_id: string; conclusion: AnomalyType | null; confidence: number | null; explanation: string | null; explanation_source: string | null; steps: number }[];
  disclaimer: string;
}

export interface Health { status: string; database: string; ollama: string; service: string; tagline: string; version: string }
export interface APIErrorBody { code: string; message: string; details?: unknown[] }
