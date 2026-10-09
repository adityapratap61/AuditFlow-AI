"""Adaptive, tool-using investigation of one unresolved transaction.

Each step's outcome decides the next step (see `decision` on every stored step). Fully deterministic;
the LLM is only used afterwards to phrase the explanation.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.agent.tools import InvestigationToolbox, ToolResult
from app.core.config import Settings
from app.domain import (AMOUNT_MISMATCH, DUPLICATE_TRANSACTION, MISSING_TRANSACTION, TIMING_DIFFERENCE, Txn, new_id)
from app.matching.scoring import MatchScore

log = logging.getLogger(__name__)


@dataclass
class StepRecord:
    step_number: int
    tool: str
    arguments: Dict[str, Any]
    result_summary: str
    candidate_ids: List[str]
    decision: Optional[str] = None


@dataclass
class InvestigationResult:
    transaction_id: str
    conclusion: str
    confidence: float
    steps: List[StepRecord] = field(default_factory=list)
    counterpart: Optional[Txn] = None
    comparison: Optional[Dict[str, Any]] = None
    score: Optional[MatchScore] = None
    duplicate_ids: List[str] = field(default_factory=list)
    rejected: List[str] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)
    explanation: str = ""
    explanation_source: str = "fallback"
    explanation_detail: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=new_id)


class _Run:
    def __init__(self, tb: InvestigationToolbox):
        self.tb = tb
        self.steps: List[StepRecord] = []

    def call(self, name: str, *args, **kwargs) -> ToolResult:
        res: ToolResult = getattr(self.tb, name)(*args, **kwargs)
        self.steps.append(StepRecord(len(self.steps) + 1, name, res.arguments, res.summary, res.ids))
        log.info("agent step %d: %s -> %s", len(self.steps), name, res.summary)
        return res

    def decide(self, text: str) -> None:
        if self.steps:
            self.steps[-1].decision = text


def investigate(txn: Txn, tb: InvestigationToolbox, s: Settings) -> InvestigationResult:
    run = _Run(tb)
    union: Dict[str, Txn] = {}
    sim_hint: Dict[str, float] = {}

    # STEP 1 - exact amount
    r1 = run.call("search_by_amount", txn)
    for c in r1.candidates:
        union[c.id] = c
    run.decide(f"{len(r1.candidates)} same-amount candidate(s); " + (
        "narrowing by reference and date" if r1.candidates else "no identical amount - will try references and descriptions"))

    # STEP 2 - reference check
    ref_hits: List[Txn] = []
    if txn.ref_keys:
        r2 = run.call("search_by_reference", txn)
        ref_hits = r2.candidates
        for c in ref_hits:
            union[c.id] = c
        run.decide("reference match found - strong evidence of the same transaction" if ref_hits
                   else "no counterpart shares a reference")

    # STEP 3 - nearby dates among same-amount candidates (strict, then relaxed)
    focus: List[Txn] = []
    if r1.candidates:
        r3 = run.call("search_by_date_range", txn, s.strict_date_tolerance_days, r1.candidates)
        focus = r3.candidates
        if focus:
            run.decide(f"{len(focus)} candidate(s) within strict ±{s.strict_date_tolerance_days} day(s)")
        else:
            r3b = run.call("search_by_date_range", txn, s.relaxed_date_tolerance_days, r1.candidates)
            focus = r3b.candidates
            run.decide(f"{len(focus)} candidate(s) within relaxed ±{s.relaxed_date_tolerance_days} day(s)" if focus
                       else "no same-amount candidate within relaxed date tolerance")

    # STEP 4 - relaxed-tolerance retry (date + amount) when nothing convincing so far
    if not focus and not ref_hits:
        r4 = run.call("retry_with_relaxed_tolerance", txn)
        for c in r4.candidates:
            union[c.id] = c
        focus = r4.candidates
        run.decide(f"relaxed retry produced {len(focus)} candidate(s)" if focus else "relaxed retry found nothing")

    # STEP 5 - description search if still nothing
    if not focus and not ref_hits:
        r5 = run.call("search_by_description", txn)
        for c in r5.candidates:
            union[c.id] = c
        focus = r5.candidates
        sim_hint.update(r5.data.get("similarity", {}))
        run.decide(f"{len(focus)} similar-vendor candidate(s) in the wider window" if focus else "no similar vendor found")

    pool = list({c.id: c for c in (ref_hits + focus)}.values())
    best: Optional[Txn] = None
    comp_res: Optional[ToolResult] = None
    if pool:
        r6 = run.call("fuzzy_search_transactions", txn, pool)
        ranked = r6.candidates
        # prefer reference hits, then description similarity
        ranked.sort(key=lambda c: (c.id not in {h.id for h in ref_hits},))
        best = ranked[0]
        run.decide(f"best candidate selected (description similarity {r6.data['similarity'][best.id]:.0f}%)")
        comp_res = run.call("compare_transactions", txn, best)

    # STEP 7 - duplicates in same source
    r7 = run.call("check_duplicates", txn)

    # conclusion --------------------------------------------------------------------------------------------
    conclusion, confidence, counterpart, comparison, score = MISSING_TRANSACTION, 0.7, None, None, None
    rejected: List[str] = []
    if best is not None and comp_res is not None:
        cmp = comp_res.data["comparison"]
        sc: MatchScore = comp_res.data["score"]
        sim, ref_ok, dd = cmp["description_similarity"], cmp["reference_match"], cmp["date_difference_days"]
        if cmp["amount_equal"]:
            if (ref_ok or sim >= 60) and dd > s.strict_date_tolerance_days:
                conclusion = TIMING_DIFFERENCE
                confidence = min(0.98, 0.55 + 0.25 * sim / 100 + (0.15 if ref_ok else 0.0) + (0.03 if dd <= s.relaxed_date_tolerance_days else 0.0))
            elif (ref_ok or sim >= 60) and dd <= s.strict_date_tolerance_days:
                conclusion = TIMING_DIFFERENCE if dd > 0 else MISSING_TRANSACTION
                confidence = 0.6
            else:
                rejected.append(f"same amount but description similarity only {sim:.0f}% and no reference")
        else:
            if ref_ok or (sim >= 80 and dd <= s.relaxed_date_tolerance_days):
                conclusion = AMOUNT_MISMATCH
                confidence = min(0.95, 0.5 + 0.25 * sim / 100 + (0.2 if ref_ok else 0.0))
            else:
                rejected.append(f"amount differs and evidence is weak (description {sim:.0f}%, no reference)")
        if conclusion in (TIMING_DIFFERENCE, AMOUNT_MISMATCH):
            counterpart, comparison, score = best, cmp, sc
            run.decide(f"counterpart accepted -> {conclusion}")
        else:
            run.decide("candidate rejected as coincidental: " + "; ".join(rejected))
    if counterpart is None and r7.candidates:
        conclusion = DUPLICATE_TRANSACTION
        confidence = max(r7.data["confidence"].values())
        run.decide("probable duplicate record(s) found in the same source")
    elif counterpart is None:
        confidence = 0.8 if not pool else 0.65
        run.decide("no credible counterpart or duplicate -> MISSING_TRANSACTION")

    result = InvestigationResult(
        transaction_id=txn.id, conclusion=conclusion, confidence=round(confidence, 2), steps=run.steps,
        counterpart=counterpart, comparison=comparison, score=score, duplicate_ids=r7.ids if conclusion == DUPLICATE_TRANSACTION else [],
        rejected=rejected)
    result.evidence = build_evidence(txn, result, tb, r7)
    return result


def build_evidence(txn: Txn, res: InvestigationResult, tb: InvestigationToolbox, dup: ToolResult) -> Dict[str, Any]:
    s = tb.s
    ev: Dict[str, Any] = {
        "transaction": txn.brief(),
        "conclusion": res.conclusion,
        "confidence": res.confidence,
        "counterpart": res.counterpart.brief() if res.counterpart else None,
        "comparison": res.comparison,
        "duplicates": [d.brief() for d in dup.candidates][:5] if res.conclusion == DUPLICATE_TRANSACTION else [],
        "rejected_candidates": res.rejected,
        "tolerances": {"strict_date_days": s.strict_date_tolerance_days, "relaxed_date_days": s.relaxed_date_tolerance_days,
                       "high_value_threshold": s.high_value_threshold},
        "steps": [{"tool": st.tool, "result": st.result_summary} for st in res.steps],
    }
    if res.conclusion == DUPLICATE_TRANSACTION and dup.candidates:
        ev["duplicate_confidence"] = max(dup.data["confidence"].values())
    return ev
