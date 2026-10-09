from dataclasses import replace

from app.anomaly.detector import detect_anomalies
from app.domain import (AMOUNT_MISMATCH, DUPLICATE_TRANSACTION, HIGH_VALUE_MISMATCH, MISSING_TRANSACTION,
                        POTENTIALLY_SUSPICIOUS, SUSPICIOUS_DISCLAIMER, TIMING_DIFFERENCE)
from app.matching.matcher import Matcher
from tests.helpers import mk


def detect(settings, bank, acct):
    matches = Matcher(settings).match(bank, acct)
    return detect_anomalies(bank, acct, matches, settings)


def types(anoms, **kw):
    return [a.anomaly_type for a in anoms]


def test_missing_transaction_both_sides(settings):
    bank, acct = [mk("BANK", "2025-01-02", "NEFT-LONE VENDOR", 1234)], [mk("ACCOUNTING", "2025-01-20", "Other Co", 777)]
    anoms, _ = detect(settings, bank, acct)
    assert sorted((a.source, a.anomaly_type) for a in anoms) == [("ACCOUNTING", MISSING_TRANSACTION), ("BANK", MISSING_TRANSACTION)]


def test_duplicate_detection_group(settings):
    b = [mk("BANK", "2025-01-14", "NEFT-ZENITH LOGISTICS", 52000), mk("BANK", "2025-01-14", "NEFT-ZENITH LOGISTICS", 52000)]
    a = [mk("ACCOUNTING", "2025-01-14", "Zenith Logistics", 52000)]
    anoms, groups = detect(settings, b, a)
    dup = [x for x in anoms if x.anomaly_type == DUPLICATE_TRANSACTION]
    assert len(dup) == 1 and len(groups) == 1 and len(groups[0].txn_ids) == 2
    assert groups[0].confidence >= settings.duplicate_min_confidence and groups[0].explanation
    assert MISSING_TRANSACTION not in types(anoms)  # the duplicate is explained, not double-reported


def test_duplicate_requires_matching_amount_and_description(settings):
    b = [mk("BANK", "2025-01-14", "NEFT-ALPHA", 100), mk("BANK", "2025-01-14", "NEFT-BETA", 100), mk("BANK", "2025-01-14", "NEFT-ALPHA", 101)]
    _, groups = detect(settings, b, [])
    assert groups == []


def test_amount_mismatch_and_high_value(settings):
    b = [mk("BANK", "2025-01-16", "NEFT-HIGH TENSION CABLES", 450000, ref="ICICN25016777001"),
         mk("BANK", "2025-01-15", "NEFT-VERMA ENGINEERING WORKS INV1015", 76500)]
    a = [mk("ACCOUNTING", "2025-01-16", "High Tension Cables", 300000, ref="ICICN25016777001"),
         mk("ACCOUNTING", "2025-01-15", "Verma Engineering Works Invoice INV1015", 74500)]
    anoms, _ = detect(settings, b, a)
    t = types(anoms)
    assert t.count(AMOUNT_MISMATCH) == 2 and t.count(HIGH_VALUE_MISMATCH) == 1  # only the 1,50,000 difference
    hv = next(x for x in anoms if x.anomaly_type == HIGH_VALUE_MISMATCH)
    assert hv.severity == "HIGH" and hv.details["amount_difference"] == 150000
    loose = replace(settings, high_value_threshold=1_000_000)
    assert HIGH_VALUE_MISMATCH not in types(detect(loose, b, a)[0])


def test_timing_difference(settings):
    loose = replace(settings, strict_date_tolerance_days=3)  # pairing allowed, but >1 day is still flagged below
    b, a = [mk("BANK", "2025-01-08", "NEFT-KUMAR TRANSPORT", 22500)], [mk("ACCOUNTING", "2025-01-10", "Kumar Transport", 22500)]
    anoms, _ = detect_anomalies(b, a, Matcher(loose).match(b, a), replace(loose, strict_date_tolerance_days=1))
    assert types(anoms) == [TIMING_DIFFERENCE] and anoms[0].severity == "LOW"


def test_suspicious_is_conservative(settings):
    acct = [mk("ACCOUNTING", "2025-01-02", "Known Vendor", 10)]
    single = [mk("BANK", "2025-01-05", "NEFT-KNOWN VENDOR2", 95000)]  # only 'near threshold'
    assert POTENTIALLY_SUSPICIOUS not in types(detect(settings, single, acct)[0])
    flagged = [mk("BANK", "2025-01-17", "CASH WITHDRAWAL SELF CHQ 000451", 120000)]
    anoms, _ = detect(settings, flagged, acct)
    s = next(x for x in anoms if x.anomaly_type == POTENTIALLY_SUSPICIOUS)
    assert SUSPICIOUS_DISCLAIMER in s.description and "fraud" not in s.description.lower()
    assert s.severity == "HIGH" and HIGH_VALUE_MISMATCH in types(anoms)  # unmatched >= threshold


def test_clean_data_has_no_anomalies(settings):
    b, a = [mk("BANK", "2025-01-02", "UPI-SWIGGY", 3250)], [mk("ACCOUNTING", "2025-01-02", "Swiggy", 3250)]
    assert detect(settings, b, a)[0] == []
