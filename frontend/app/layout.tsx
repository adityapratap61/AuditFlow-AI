import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import { ToastProvider } from "@/components/ui/Toast";
import { RunProvider } from "@/hooks/useRun";
import { AppShell } from "@/components/layout/AppShell";

export const metadata: Metadata = {
  title: "AuditFlow AI — Reconcile. Investigate. Resolve.",
  description: "AI-Powered Financial Reconciliation & Anomaly Investigation",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <ToastProvider>
          <RunProvider>
            <AppShell>{children}</AppShell>
          </RunProvider>
        </ToastProvider>
      </body>
    </html>
  );
}
