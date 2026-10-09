"use client";
import { Card, ErrorState, PageHeader, Spinner } from "@/components/ui";
import { RunGate } from "@/components/layout/RunGate";
import { TransactionTable } from "@/components/transactions/TransactionTable";
import { useRun } from "@/hooks/useRun";
import { useTransactions } from "@/hooks/useTransactions";
import { useAnomalies } from "@/hooks/useAnomalies";

function Content() {
  const { runId } = useRun();
  const tx = useTransactions(runId);
  const an = useAnomalies(runId);
  if (tx.loading || an.loading) return <Card><Spinner label="Loading transactions…" /></Card>;
  if (tx.error || an.error) return <ErrorState message={(tx.error ?? an.error)!} network={tx.network || an.network} onRetry={() => { tx.reload(); an.reload(); }} />;
  if (!tx.data) return null;
  return <Card><TransactionTable transactions={tx.data.transactions} matches={tx.data.matches} anomalies={an.anomalies} /></Card>;
}

export default function TransactionsPage() {
  return (
    <>
      <PageHeader title="Transactions" subtitle="Search, filter and review every reconciled transaction" />
      <RunGate what="transactions"><Content /></RunGate>
    </>
  );
}
