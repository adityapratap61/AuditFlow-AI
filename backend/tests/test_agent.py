import json

import pytest

from app.domain import (AMOUNT_MISMATCH, DUPLICATE_TRANSACTION, MISSING_TRANSACTION, POTENTIALLY_SUSPICIOUS,
                        TIMING_DIFFERENCE)
from app.llm.explainer import Explainer, validate_explanation
from app.llm.fallback import fallback_explanation, fallback_summary
from app.llm.ollama_client import OllamaClient, OllamaError
from tests.helpers import mk, run_pipeline


class FakeClient:
    """Stand-in for OllamaClient (tests never need a running Ollama)."""

    def __init__(self, available=True, payload=None, error=None):
        self.available, self.payload, self.error, self.calls = available, payload, error, 0

    def is_available(self, force=False):
        return self.available

    def generate_json(self, prompt, system=None):
        self.calls += 1
        if self.error:
            raise self.error
        return self.payload


def timing_case():
    bank = [mk("BANK", "2025-01-10", "NEFT-KUMAR TRANSPORT", 75000), mk("BANK", "2025-01-10", "UPI-OTHER", 75000, ref="UTR000111222")]
    acct = [mk("ACCOUNTING", "2025-01-12", "Kumar Transport", 75000), mk("ACCOUNTING", "2025-01-10", "Other", 75000, ref="UTR000111222")]
    return bank, acct


def test_agent_resolves_timing_difference_with_trail(settings):
    bank, acct = timing_case()
    _, _, _, out = run_pipeline(settings, bank, acct, Explainer(settings, FakeClient(available=False)))
    anomaly = next(a for a in out.anomalies if a.transaction_id == bank[0].id)
    assert anomaly.anomaly_type == TIMING_DIFFERENCE and anomaly.related_transaction_id == acct[0].id
    assert not [a for a in out.anomalies if a.anomaly_type == MISSING_TRANSACTION]  # counterpart no longer 'missing'
    inv = next(i for i in out.investigations if i.transaction_id == bank[0].id)
    tools = [s.tool for s in inv.steps]
    assert tools[0] == "search_by_amount" and "search_by_date_range" in tools and "compare_transactions" in tools
    assert all(s.result_summary for s in inv.steps) and any(s.decision for s in inv.steps)  # decisions are recorded
    assert inv.conclusion == TIMING_DIFFERENCE and inv.counterpart.id == acct[0].id
    assert "timing difference" in inv.explanation.lower() and "manual verification" in inv.explanation.lower()
    assert inv.explanation_source == "fallback" and out.primary_anomaly[inv.id] == anomaly.id
    assert any(m.matched_by == "AGENT" and m.accounting_id == acct[0].id for m in out.matches)


def test_agent_retries_with_relaxed_tolerance(settings):
    bank = [mk("BANK", "2025-01-10", "NEFT-ALPHA FREIGHT LINES", 41000)]
    acct = [mk("ACCOUNTING", "2025-01-13", "Alpha Freight Lines", 41000)]  # 3 days = relaxed limit
    _, _, _, out = run_pipeline(settings, bank, acct)
    assert out.anomalies[0].anomaly_type == TIMING_DIFFERENCE
    assert out.investigations[0].steps[0].tool == "search_by_amount"


def test_agent_missing_transaction_and_suspicious_flag(settings):
    bank = [mk("BANK", "2025-01-17", "CASH WITHDRAWAL SELF CHQ 000451", 120000)]
    acct = [mk("ACCOUNTING", "2025-01-02", "Known Vendor", 10)]
    _, _, _, out = run_pipeline(settings, bank, acct)
    inv = next(i for i in out.investigations if i.transaction_id == bank[0].id)
    assert inv.conclusion == MISSING_TRANSACTION
    assert {s.tool for s in inv.steps} >= {"search_by_amount", "retry_with_relaxed_tolerance", "search_by_description", "check_duplicates"}
    assert "Potentially suspicious transaction requiring manual verification." in inv.explanation
    assert any(a.anomaly_type == POTENTIALLY_SUSPICIOUS for a in out.anomalies)


def test_agent_amount_mismatch_and_duplicate(settings):
    bank = [mk("BANK", "2025-01-16", "NEFT-HIGH TENSION CABLES", 450000, ref="ICICN25016777001"),
            mk("BANK", "2025-01-14", "NEFT-ZENITH", 52000), mk("BANK", "2025-01-14", "NEFT-ZENITH", 52000)]
    acct = [mk("ACCOUNTING", "2025-01-16", "High Tension Cables", 300000, ref="ICICN25016777001"),
            mk("ACCOUNTING", "2025-01-14", "Zenith", 52000)]
    _, _, _, out = run_pipeline(settings, bank, acct)
    kinds = {a.anomaly_type for a in out.anomalies}
    assert {AMOUNT_MISMATCH, DUPLICATE_TRANSACTION} <= kinds
    dup = next(i for i in out.investigations if i.conclusion == DUPLICATE_TRANSACTION)
    assert "duplicate" in dup.explanation.lower()


def test_fallback_when_ollama_unavailable(settings):
    bank, acct = timing_case()
    client = FakeClient(available=False)
    _, _, _, out = run_pipeline(settings, bank, acct, Explainer(settings, client))
    assert client.calls == 0 and all(i.explanation_source == "fallback" and i.explanation for i in out.investigations)
    real = OllamaClient(settings.__class__(ollama_base_url="http://127.0.0.1:9", ollama_model="x"))
    ex = Explainer(settings, real)  # genuinely unreachable server must not raise
    assert ex.explain(out.investigations[0].evidence)["source"] == "fallback"


def test_fallback_text_is_evidence_based(settings):
    bank, acct = timing_case()
    _, _, _, out = run_pipeline(settings, bank, acct)
    inv = next(i for i in out.investigations if i.conclusion == TIMING_DIFFERENCE)
    text = fallback_explanation(inv.evidence)["explanation"]
    assert "₹75,000.00" in text and "2 day(s)" in text and "timing difference" in text
    assert "fraud" not in fallback_summary({"total_bank_transactions": 1, "total_accounting_transactions": 1, "matched": 1,
                                            "likely_matches": 0, "review_required": 0, "unmatched": 0, "total_anomalies": 0, "high_risk": 0})


def _evidence(settings):
    bank, acct = timing_case()
    return run_pipeline(settings, bank, acct)[3].investigations[0].evidence


def _good(ev):
    amt = f"{ev['transaction']['amount']:,.2f}"
    return {"explanation": f"The bank transaction of {amt} dated {ev['transaction']['date']} has a likely counterpart. It looks like a timing difference.",
            "evidence_points": [f"Amount {amt}"], "inference": "Probable timing difference.",
            "recommended_action": "Confirm the posting date; manual verification recommended."}


def test_llm_valid_output_is_used(settings):
    ev = _evidence(settings)
    client = FakeClient(payload=_good(ev))
    out = Explainer(settings, client).explain(ev)
    assert out["source"] == "ollama" and client.calls == 1


@pytest.mark.parametrize("mutate", [
    lambda d: {**d, "explanation": d["explanation"] + " An amount of 99,999.00 was also moved."},   # invented number
    lambda d: {**d, "explanation": "This transaction is confirmed fraud and should be reported right away."},
    lambda d: {"explanation": "short"},                                                              # missing keys
    lambda d: {**d, "evidence_points": "not a list"},
])
def test_llm_invalid_output_falls_back(settings, mutate):
    ev = _evidence(settings)
    out = Explainer(settings, FakeClient(payload=mutate(_good(ev)))).explain(ev)
    assert out["source"] == "fallback" and out["explanation"]
    with pytest.raises(ValueError):
        validate_explanation(mutate(_good(ev)), ev)


def test_llm_errors_fall_back_and_budget_is_respected(settings):
    ev = _evidence(settings)
    assert Explainer(settings, FakeClient(error=OllamaError("boom"))).explain(ev)["source"] == "fallback"
    client = FakeClient(payload=_good(ev))
    assert Explainer(settings, client, use_llm=False).explain(ev)["source"] == "fallback" and client.calls == 0
    assert Explainer(settings, client, max_calls=0).explain(ev)["source"] == "fallback" and client.calls == 0
    text, src = Explainer(settings, FakeClient(payload={"summary": "ok"})).summarize(
        {"total_bank_transactions": 1, "total_accounting_transactions": 1, "matched": 1, "likely_matches": 0,
         "review_required": 0, "unmatched": 0, "total_anomalies": 0, "high_risk": 0})
    assert src == "fallback" and "AuditFlow AI" in text


def test_evidence_is_json_serialisable(settings):
    json.dumps(_evidence(settings))
