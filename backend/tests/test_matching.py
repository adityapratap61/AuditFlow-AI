import time
from dataclasses import replace

from app.domain import LIKELY_MATCH, MATCHED, REVIEW_REQUIRED, UNMATCHED
from app.matching.fuzzy_matcher import description_similarity, text_similarity
from app.matching.matcher import Matcher
from app.matching.scoring import ScoreWeights, classify_score, score_pair
from app.matching.tolerance import relaxed_tolerance, strict_tolerance
from tests.helpers import mk


def test_fuzzy_vendor_variation_scores_high():
    b, a = mk("BANK", "2025-01-02", "NEFT-ABC SUPPLIERS PVT LTD-INV1001", 100), mk("ACCOUNTING", "2025-01-02", "ABC Supplier", 100)
    assert description_similarity(b, a) >= 90
    assert text_similarity("abc supplier", "zenith logistics") < 55


def test_level1_reference_match(settings):
    b = mk("BANK", "2025-01-02", "NEFT-X", 500, ref="UTR998877665")
    a = mk("ACCOUNTING", "2025-01-09", "Totally different text", 500, ref="utr 998877665")
    r = Matcher(settings).match([b], [a])[0]
    assert r.accounting_id == a.id and r.level == 1 and r.status != UNMATCHED and any("reference" in x for x in r.reasons)


def test_exact_amount_and_date_is_matched(settings):
    b, a = mk("BANK", "2025-01-02", "UPI-SWIGGY", 3250), mk("ACCOUNTING", "2025-01-02", "Swiggy", 3250)
    r = Matcher(settings).match([b], [a])[0]
    assert r.status == MATCHED and r.score >= 90 and r.date_diff_days == 0 and r.amount_difference == 0
    assert set(r.signals) == {"amount_score", "date_score", "description_score", "reference_score"}
    assert r.description_similarity and r.reasons


def test_strict_vs_relaxed_date_tolerance(settings):
    b, a = mk("BANK", "2025-01-10", "NEFT-KUMAR TRANSPORT", 22500), mk("ACCOUNTING", "2025-01-12", "Kumar Transport", 22500)
    assert Matcher(settings).match([b], [a])[0].accounting_id is None  # 2 days > strict (1)
    sc = score_pair(b, a, settings)  # relaxed scoring still credits the pair
    assert sc.date_diff_days == 2 and sc.signals["date"] == settings.date_score_weight * 0.5 and sc.total >= settings.review_threshold
    loose = replace(settings, strict_date_tolerance_days=2)
    assert Matcher(loose).match([b], [a])[0].status == MATCHED
    assert strict_tolerance(settings).date_ok(b.date, a.date) is False and relaxed_tolerance(settings).date_ok(b.date, a.date)


def test_scoring_weights_configurable(settings):
    b, a = mk("BANK", "2025-01-02", "ABC", 100), mk("ACCOUNTING", "2025-01-02", "ABC", 100)
    assert ScoreWeights.from_settings(settings) == ScoreWeights(40, 20, 20, 20)
    custom = replace(settings, amount_score_weight=10, date_score_weight=10, description_score_weight=10, reference_score_weight=70)
    assert ScoreWeights.from_settings(custom).reference == 70
    assert score_pair(b, a, custom).total == 100.0


def test_classification_thresholds_configurable(settings):
    assert [classify_score(x, settings) for x in (95, 90, 80, 75, 60, 50, 49.9)] == [
        MATCHED, MATCHED, LIKELY_MATCH, LIKELY_MATCH, REVIEW_REQUIRED, REVIEW_REQUIRED, UNMATCHED]
    assert classify_score(80, replace(settings, match_threshold=80)) == MATCHED


def test_amount_difference_not_matched_without_support(settings):
    b, a = mk("BANK", "2025-01-02", "NEFT-VERMA ENGINEERING", 76500), mk("ACCOUNTING", "2025-01-02", "Verma Engineering Works", 74500)
    r = Matcher(settings).match([b], [a])[0]
    assert r.accounting_id == a.id and r.status != MATCHED and r.amount_difference == 2000


def test_one_to_one_assignment(settings):
    bank = [mk("BANK", "2025-01-02", "UPI-ZOMATO", 100), mk("BANK", "2025-01-02", "UPI-ZOMATO", 100)]
    res = Matcher(settings).match(bank, [mk("ACCOUNTING", "2025-01-02", "Zomato", 100)])
    assert sorted(r.accounting_id is None for r in res) == [False, True]


def test_performance_5000x5000(settings):
    import datetime as dt
    base = dt.date(2025, 1, 1)
    bank, acct = [], []
    for i in range(5000):
        d = (base + dt.timedelta(days=i % 90)).isoformat()
        amt, name = 100 + (i * 37) % 9000 + (i % 7) * 0.5, f"VENDOR{i % 400} TRADERS"
        bank.append(mk("BANK", d, f"NEFT-{name}", amt))
        acct.append(mk("ACCOUNTING", d, name.title(), amt))
    t0 = time.perf_counter()
    res = Matcher(settings).match(bank, acct)
    assert time.perf_counter() - t0 < 30
    assert sum(r.status == MATCHED for r in res) > 4500
