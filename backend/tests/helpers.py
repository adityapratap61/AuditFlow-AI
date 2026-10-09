from app.normalization.normalizer import build_transaction


def mk(source, day, desc, amount, ref=None, ttype="DEBIT", **kw):
    """Build a normalised transaction: mk('BANK', '2025-01-10', 'NEFT-ABC SUPPLIERS', 5000)."""
    kwargs = {"debit" if ttype == "DEBIT" else "credit": amount}
    return build_transaction(source, day, desc, reference=ref, **kwargs, **kw)


def run_pipeline(settings, bank, acct, explainer=None):
    from app.agent.reconciliation_agent import ReconciliationAgent
    from app.anomaly.detector import detect_anomalies
    from app.matching.matcher import Matcher
    matches = Matcher(settings).match(bank, acct)
    anomalies, groups = detect_anomalies(bank, acct, matches, settings)
    return matches, anomalies, groups, ReconciliationAgent(settings, bank, acct, matches, anomalies, explainer).run()
