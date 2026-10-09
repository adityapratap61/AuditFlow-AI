"""ReconciliationAgent: investigates every transaction that carries an anomaly, refines classifications,
applies relaxed-tolerance resolutions to the match set and attaches evidence-based explanations."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set

from app.agent.investigation import InvestigationResult, StepRecord, build_evidence, investigate
from app.agent.tools import InvestigationToolbox, ToolResult
from app.anomaly import rules
from app.anomaly.detector import high_value_description
from app.core.config import Settings
from app.domain import (ACCOUNTING, AMOUNT_MISMATCH, BANK, DUPLICATE_TRANSACTION, HIGH_VALUE_MISMATCH,
                        MISSING_TRANSACTION, POTENTIALLY_SUSPICIOUS, REVIEW_REQUIRED, TIMING_DIFFERENCE, UNMATCHED, Anomaly, MatchResult,
                        Txn, new_id)
from app.llm.explainer import Explainer
from app.matching.matcher import TransactionIndex, to_match_result
from app.matching.scoring import classify_score
from app.utils.amounts import format_money

log = logging.getLogger(__name__)
_FLAG_TYPES = (HIGH_VALUE_MISMATCH, POTENTIALLY_SUSPICIOUS)
_PRIORITY = [DUPLICATE_TRANSACTION, AMOUNT_MISMATCH, TIMING_DIFFERENCE, MISSING_TRANSACTION, HIGH_VALUE_MISMATCH,
             POTENTIALLY_SUSPICIOUS]


@dataclass
class AgentOutcome:
    matches: List[MatchResult]
    anomalies: List[Anomaly]
    investigations: List[InvestigationResult] = field(default_factory=list)
    primary_anomaly: Dict[str, str] = field(default_factory=dict)  # investigation id -> anomaly id


def apply_explanation(res: InvestigationResult, explainer: Optional[Explainer], flags: List[str]) -> None:
    from app.llm.fallback import fallback_explanation
    out = explainer.explain(res.evidence, flags) if explainer else fallback_explanation(res.evidence, flags)
    res.explanation = out["explanation"]
    res.explanation_source = out.get("source", "fallback")
    res.explanation_detail = {k: out[k] for k in ("evidence_points", "inference", "recommended_action") if k in out}


class ReconciliationAgent:
    def __init__(self, settings: Settings, bank: Sequence[Txn], accounting: Sequence[Txn],
                 matches: Sequence[MatchResult], anomalies: Sequence[Anomaly], explainer: Optional[Explainer] = None):
        self.s = settings
        self.bank, self.accounting = list(bank), list(accounting)
        self.matches = list(matches)
        self.anomalies = list(anomalies)
        self.explainer = explainer
        self.bank_idx, self.acct_idx = TransactionIndex(self.bank), TransactionIndex(self.accounting)
        self.by_id: Dict[str, Txn] = {**self.bank_idx.by_id, **self.acct_idx.by_id}
        self.match_by_bank: Dict[str, MatchResult] = {m.bank_id: m for m in self.matches}
        self.pair_of: Dict[str, str] = {}  # txn id -> counterpart id for matched pairs (both directions)
        for m in self.matches:
            if m.accounting_id and m.status != UNMATCHED:
                self.pair_of[m.bank_id], self.pair_of[m.accounting_id] = m.accounting_id, m.bank_id

    # ------------------------------------------------------------------ helpers
    def _taken_for(self, txn: Txn) -> Set[str]:
        want_src = ACCOUNTING if txn.source == BANK else BANK
        own = self.pair_of.get(txn.id)
        return {i for i in self.pair_of if i != own and self.by_id[i].source == want_src}

    def _own(self, tid: str) -> List[Anomaly]:
        return [a for a in self.anomalies if a.transaction_id == tid]

    def _drop(self, pred) -> None:
        self.anomalies = [a for a in self.anomalies if not pred(a)]

    def _record_pair(self, txn: Txn, other: Txn, res: InvestigationResult) -> None:
        bank, acct = (txn, other) if txn.source == BANK else (other, txn)
        mr = to_match_result(bank, acct, res.score, self.s, 5, matched_by="AGENT")
        mr.reasons = mr.reasons + [f"resolved by investigation agent as {res.conclusion}"]
        if mr.status == UNMATCHED:  # agent evidence supports the pairing -> needs human review, not 'unmatched'
            mr.status = REVIEW_REQUIRED
        self.match_by_bank[bank.id] = mr
        self.matches = [mr if m.bank_id == bank.id else m for m in self.matches]
        self.pair_of[bank.id], self.pair_of[acct.id] = acct.id, bank.id

    def _apply_resolution(self, txn: Txn, primary: Anomaly, res: InvestigationResult) -> None:
        cp = res.counterpart
        assert cp is not None and res.score is not None
        cmp = res.comparison or {}
        cur = txn.currency
        self._record_pair(txn, cp, res)
        # the counterpart is no longer "missing"; this record is no longer a lone/suspicious record
        self._drop(lambda a: a.transaction_id == cp.id and a.anomaly_type == MISSING_TRANSACTION)
        self._drop(lambda a: a.transaction_id == txn.id and a.anomaly_type == POTENTIALLY_SUSPICIOUS)
        self._drop(lambda a: a.transaction_id == txn.id and a.anomaly_type == HIGH_VALUE_MISMATCH
                   and a.details.get("unmatched"))
        primary.anomaly_type = res.conclusion
        primary.related_transaction_id = cp.id
        primary.confidence = res.confidence
        primary.details = {**primary.details, "agent_resolved": True, "match_score": res.score.total,
                           "date_diff_days": cmp.get("date_difference_days"),
                           "amount_difference": cmp.get("amount_difference")}
        bank_t, acct_t = (txn, cp) if txn.source == BANK else (cp, txn)
        if res.conclusion == TIMING_DIFFERENCE:
            primary.description = (f"Likely the same transaction: identical amount {format_money(txn.amount, cur)} recorded "
                                   f"{cmp.get('date_difference_days')} day(s) apart (bank {bank_t.date.isoformat()}, "
                                   f"accounting {acct_t.date.isoformat()}).")
            primary.severity = "LOW"
        else:
            diff = cmp.get("amount_difference", 0.0)
            primary.description = (f"Likely the same transaction with different amounts: bank "
                                   f"{format_money(bank_t.amount, cur)} vs accounting {format_money(acct_t.amount, cur)} "
                                   f"(difference {format_money(diff, cur)}).")
            primary.severity = rules.severity_for(AMOUNT_MISMATCH, diff, self.s)
            if rules.is_high_value(diff, self.s):
                self.anomalies.append(Anomaly(
                    id=new_id(), transaction_id=txn.id, related_transaction_id=cp.id, anomaly_type=HIGH_VALUE_MISMATCH,
                    severity="HIGH", source=txn.source, confidence=res.confidence,
                    description=high_value_description(diff, self.s, cur),
                    details={"amount_difference": diff, "threshold": self.s.high_value_threshold}))

    def _align_with_detector(self, txn: Txn, primary: Anomaly, res: InvestigationResult, tb: InvestigationToolbox) -> None:
        """Detector classified pair/duplicate anomalies deterministically; keep that type, add supporting evidence."""
        rel = self.by_id.get(primary.related_transaction_id or "")
        dup = ToolResult("check_duplicates", {}, [], "", {"confidence": {}})
        if rel is None:
            return
        if primary.anomaly_type == DUPLICATE_TRANSACTION:
            conf = float(primary.details.get("confidence") or primary.confidence or 0.7)
            dup = ToolResult("check_duplicates", {}, [rel], "", {"confidence": {rel.id: conf}})
            res.conclusion, res.confidence, res.counterpart, res.comparison = DUPLICATE_TRANSACTION, round(conf, 2), None, None
            res.duplicate_ids = [rel.id]
        else:
            cr = tb.compare_transactions(txn, rel)
            res.steps.append(StepRecord(len(res.steps) + 1, cr.tool, cr.arguments, cr.summary, cr.ids,
                                        f"match-engine pairing confirmed as {primary.anomaly_type}"))
            res.conclusion, res.confidence = primary.anomaly_type, round(primary.confidence or 0.8, 2)
            res.counterpart, res.comparison, res.score = rel, cr.data["comparison"], cr.data["score"]
        res.evidence = build_evidence(txn, res, tb, dup)

    # ------------------------------------------------------------------ main loop
    def run(self) -> AgentOutcome:
        order = []
        seen = set()
        for a in self.anomalies:
            if a.transaction_id not in seen:
                seen.add(a.transaction_id)
                order.append(a.transaction_id)
        order.sort(key=lambda i: (self.by_id[i].source != BANK, -self.by_id[i].amount))
        results: List[InvestigationResult] = []
        for tid in order:
            own = self._own(tid)
            if not own:
                continue  # resolved as the counterpart of an earlier investigation
            txn = self.by_id[tid]
            primary = sorted(own, key=lambda a: _PRIORITY.index(a.anomaly_type))[0]
            if txn.source == BANK:
                tb = InvestigationToolbox(self.s, self.acct_idx, self.bank_idx, self._taken_for(txn))
            else:
                tb = InvestigationToolbox(self.s, self.bank_idx, self.acct_idx, self._taken_for(txn))
            log.info("Investigating %s transaction (anomaly=%s)", txn.source, primary.anomaly_type)
            res = investigate(txn, tb, self.s)
            if primary.anomaly_type == MISSING_TRANSACTION:
                if res.conclusion in (TIMING_DIFFERENCE, AMOUNT_MISMATCH) and res.counterpart is not None:
                    self._apply_resolution(txn, primary, res)
                elif res.conclusion == DUPLICATE_TRANSACTION:
                    primary.anomaly_type = DUPLICATE_TRANSACTION
                    primary.related_transaction_id = res.duplicate_ids[0] if res.duplicate_ids else None
                    primary.confidence = res.confidence
                    primary.description = "Probable duplicate: another record in the same source has the same amount, date and description."
                    primary.severity = rules.severity_for(DUPLICATE_TRANSACTION, txn.amount, self.s)
                    self._drop(lambda a: a.transaction_id == txn.id and a.anomaly_type == POTENTIALLY_SUSPICIOUS)
                else:
                    primary.confidence = res.confidence
            elif res.conclusion != primary.anomaly_type or primary.anomaly_type == DUPLICATE_TRANSACTION:
                self._align_with_detector(txn, primary, res, tb)
            own_now = self._own(tid)
            flags = [a.anomaly_type for a in own_now if a.anomaly_type in _FLAG_TYPES]
            apply_explanation(res, self.explainer, flags)
            for a in own_now:
                a.investigation_id, a.status = res.id, "INVESTIGATED"
                a.explanation, a.explanation_source = res.explanation, res.explanation_source
            results.append(res)
        # keep only investigations whose transaction still carries an anomaly
        alive = {a.transaction_id for a in self.anomalies}
        results = [r for r in results if r.transaction_id in alive]
        outcome = AgentOutcome(matches=self.matches, anomalies=self.anomalies, investigations=results)
        for r in results:
            own = sorted(self._own(r.transaction_id), key=lambda a: _PRIORITY.index(a.anomaly_type))
            outcome.primary_anomaly[r.id] = own[0].id
        log.info("Agent finished: investigations=%d anomalies=%d", len(results), len(self.anomalies))
        return outcome
