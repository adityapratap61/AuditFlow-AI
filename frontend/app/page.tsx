import Link from "next/link";
import { AlertTriangle, ArrowDown, ArrowRight, Banknote, BookOpen, Brain, CheckCircle2, FileSearch, GitCompareArrows, ShieldCheck, Workflow } from "lucide-react";
import { LinkButton, Logo } from "@/components/ui";

const FEATURES = [
  { icon: GitCompareArrows, title: "Automated Reconciliation", text: "Multi-signal matching on amount, date, reference and fuzzy descriptions with configurable tolerances." },
  { icon: Brain, title: "AI Investigation", text: "A tool-using agent searches, compares and retries with relaxed tolerance, storing every step." },
  { icon: AlertTriangle, title: "Anomaly Detection", text: "Missing, duplicate, timing, amount, high-value and potentially suspicious items flagged by rules." },
  { icon: ShieldCheck, title: "Explainable Results", text: "Facts are kept separate from AI interpretation, with the full evidence trail for each finding." },
];
const FLOW = [
  { icon: Banknote, label: "Bank Statement" }, { icon: Workflow, label: "AI Reconciliation" },
  { icon: BookOpen, label: "Accounting Records" }, { icon: FileSearch, label: "Investigation" }, { icon: CheckCircle2, label: "Resolution" },
];

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-white via-slate-50 to-slate-50">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-4 py-5 sm:px-6">
        <Logo />
        <nav className="flex items-center gap-2" aria-label="Top">
          <Link href="/dashboard" className="rounded-lg px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100">Dashboard</Link>
          <LinkButton href="/reconciliation">Start Reconciliation</LinkButton>
        </nav>
      </header>

      <main>
        <section className="mx-auto max-w-4xl px-4 pb-14 pt-12 text-center sm:px-6 sm:pt-20">
          <p className="mb-4 inline-block rounded-full bg-brand-50 px-3 py-1 text-xs font-semibold text-brand-700">AI-Powered Financial Reconciliation &amp; Anomaly Investigation</p>
          <h1 className="text-4xl font-semibold tracking-tight text-navy-900 sm:text-6xl">Reconcile. <span className="text-brand-600">Investigate.</span> <span className="text-teal-600">Resolve.</span></h1>
          <p className="mx-auto mt-5 max-w-2xl text-base text-slate-600 sm:text-lg">AI-powered bank reconciliation that automatically matches transactions, detects anomalies and investigates financial discrepancies.</p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <LinkButton href="/reconciliation" className="px-6 py-3 text-base">Start Reconciliation <ArrowRight className="h-4 w-4" aria-hidden /></LinkButton>
            <LinkButton href="/reconciliation?demo=1" variant="secondary" className="px-6 py-3 text-base">View Demo</LinkButton>
          </div>
        </section>

        <section aria-label="How it works" className="mx-auto max-w-5xl px-4 sm:px-6">
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-card">
            <ol className="flex flex-col items-stretch gap-2 md:flex-row md:items-center md:justify-between">
              {FLOW.map((s, i) => (
                <li key={s.label} className="flex flex-col items-center gap-2 md:flex-row">
                  <div className="flex min-w-[10rem] flex-col items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-center">
                    <s.icon className="h-6 w-6 text-brand-600" aria-hidden /><span className="text-sm font-medium text-navy-900">{s.label}</span>
                  </div>
                  {i < FLOW.length - 1 && <><ArrowDown className="h-4 w-4 text-slate-400 md:hidden" aria-hidden /><ArrowRight className="hidden h-4 w-4 text-slate-400 md:block" aria-hidden /></>}
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section aria-label="Features" className="mx-auto grid max-w-6xl gap-4 px-4 py-14 sm:grid-cols-2 sm:px-6 lg:grid-cols-4">
          {FEATURES.map((f) => (
            <div key={f.title} className="rounded-xl border border-slate-200 bg-white p-5 shadow-card">
              <div className="mb-3 grid h-10 w-10 place-items-center rounded-lg bg-brand-50 text-brand-600"><f.icon className="h-5 w-5" aria-hidden /></div>
              <h2 className="text-sm font-semibold text-navy-900">{f.title}</h2>
              <p className="mt-1.5 text-sm text-slate-600">{f.text}</p>
            </div>
          ))}
        </section>
      </main>
      <footer className="border-t border-slate-200 py-6 text-center text-xs text-slate-500">AuditFlow AI flags items for manual verification; it never confirms fraud.</footer>
    </div>
  );
}
