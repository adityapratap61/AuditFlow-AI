import io

import pytest

from app.llm.ollama_client import OllamaClient


def _upload(client, sample_dir, run_id=None):
    given, data = run_id, ({"run_id": run_id} if run_id else {})
    r = client.post("/api/upload/bank", files={"file": ("bank_statement.csv", (sample_dir / "bank_statement.csv").read_bytes(), "text/csv")}, data=data)
    assert r.status_code == 200, r.text
    run_id = r.json()["run_id"]
    assert r.json()["transactions_extracted"] == 34 and (given is not None or r.json()["ready_to_reconcile"] is False)
    r = client.post("/api/upload/accounting", files={"file": ("accounting_export.csv", (sample_dir / "accounting_export.csv").read_bytes(), "text/csv")}, data={"run_id": run_id})
    assert r.status_code == 200 and r.json()["ready_to_reconcile"] is True and r.json()["transactions_extracted"] == 32
    return run_id


@pytest.fixture(scope="module")
def run(client, sample_dir):
    run_id = _upload(client, sample_dir)
    r = client.post("/api/reconcile", json={"run_id": run_id})
    assert r.status_code == 200, r.text
    return r.json()


def test_reconcile_response_shape(run):
    assert run["status"] == "completed" and run["processing_time"] is not None and run["narrative"]
    s = run["summary"]
    assert s["total_bank_transactions"] == 34 and s["total_accounting_transactions"] == 32
    assert s["matched"] + s["likely_matches"] + s["review_required"] + s["unmatched"] == 34
    assert s["matched"] >= 20 and s["total_anomalies"] == len(run["anomalies"]) and s["high_risk"] >= 1
    for t in ("MISSING_TRANSACTION", "DUPLICATE_TRANSACTION", "TIMING_DIFFERENCE", "AMOUNT_MISMATCH",
              "HIGH_VALUE_MISMATCH", "POTENTIALLY_SUSPICIOUS"):
        assert s["anomaly_counts"][t] >= 1, t
    assert run["overall_status"] == "ATTENTION_REQUIRED"
    assert all(a["explanation"] and a["explanation_source"] == "fallback" for a in run["anomalies"])


def test_get_reconciliation_and_listing(client, run):
    r = client.get(f"/api/reconciliation/{run['run_id']}")
    assert r.status_code == 200 and r.json()["summary"] == run["summary"]
    assert any(x["run_id"] == run["run_id"] for x in client.get("/api/reconciliations").json()["items"])


def test_transactions_endpoints(client, run):
    rid = run["run_id"]
    page = client.get("/api/transactions", params={"run_id": rid, "source": "BANK", "limit": 10}).json()
    assert page["total"] == 34 and len(page["items"]) == 10
    unmatched = client.get("/api/transactions", params={"run_id": rid, "match_status": "UNMATCHED"}).json()
    assert unmatched["total"] >= 1
    big = client.get("/api/transactions", params={"run_id": rid, "min_amount": 100000, "search": "cash"}).json()
    assert big["total"] == 1
    detail = client.get(f"/api/transactions/{page['items'][0]['id']}")
    assert detail.status_code == 200 and detail.json()["match"] is not None
    assert client.get("/api/transactions/doesnotexist").status_code == 404


def test_matches_endpoint(client, run):
    page = client.get("/api/matches", params={"run_id": run["run_id"], "status": "MATCHED"}).json()
    assert page["total"] >= 20
    m = page["items"][0]
    assert m["score"] >= 90 and m["bank_transaction"] and m["accounting_transaction"] and m["reasons"] and "amount_score" in m["signals"]


def test_anomalies_filter_and_detail(client, run):
    rid = run["run_id"]
    high = client.get("/api/anomalies", params={"run_id": rid, "severity": "HIGH"}).json()
    assert high["total"] >= 1 and all(a["severity"] == "HIGH" for a in high["items"])
    sus = client.get("/api/anomalies", params={"run_id": rid, "anomaly_type": "POTENTIALLY_SUSPICIOUS"}).json()
    assert sus["total"] >= 1 and "manual verification" in sus["items"][0]["description"].lower()
    d = client.get(f"/api/anomalies/{sus['items'][0]['id']}").json()
    assert d["transaction"]["id"] == d["transaction_id"]
    assert client.get("/api/anomalies/nope").status_code == 404


def test_investigate_flow(client, run):
    rid = run["run_id"]
    a = client.get("/api/anomalies", params={"run_id": rid, "anomaly_type": "TIMING_DIFFERENCE"}).json()["items"][0]
    assert a["investigation_id"]  # stored during reconciliation
    stored = client.get(f"/api/investigations/{a['investigation_id']}")
    assert stored.status_code == 200 and len(stored.json()["steps"]) >= 3
    r = client.post(f"/api/investigate/{a['id']}", json={"use_llm": False})
    assert r.status_code == 200
    inv = r.json()
    assert inv["status"] == "completed" and inv["conclusion"] and inv["explanation"] and inv["anomaly_id"] == a["id"]
    assert [s["step_number"] for s in inv["steps"]] == list(range(1, len(inv["steps"]) + 1)) and inv["steps"][0]["tool"] == "search_by_amount"
    assert client.get(f"/api/investigations/{inv['id']}").json()["id"] == inv["id"]
    assert client.get("/api/anomalies/" + a["id"]).json()["status"] == "INVESTIGATED"
    assert client.post("/api/investigate/nope").status_code == 404
    assert client.get("/api/investigations/nope").status_code == 404
    assert client.get("/api/investigations", params={"run_id": rid}).json()


def test_investigation_uses_ollama_when_available(client, run, monkeypatch):
    a = client.get("/api/anomalies", params={"run_id": run["run_id"], "anomaly_type": "MISSING_TRANSACTION"}).json()["items"][0]
    monkeypatch.setattr(OllamaClient, "is_available", lambda self, force=False: True)
    monkeypatch.setattr(OllamaClient, "generate_json", lambda self, prompt, system=None: {"explanation": "bad"})
    inv = client.post(f"/api/investigate/{a['id']}", json={"use_llm": True}).json()
    assert inv["explanation_source"] == "fallback"  # invalid LLM output -> deterministic fallback, no crash


def test_report_json_and_csv(client, run):
    rep = client.get(f"/api/report/{run['run_id']}")
    assert rep.status_code == 200
    body = rep.json()
    assert body["report_metadata"]["product"] == "AuditFlow AI" and body["report_metadata"]["tagline"] == "Reconcile. Investigate. Resolve."
    assert body["overall_status"] == "ATTENTION_REQUIRED" and body["high_value_mismatches"] and body["suspicious_transactions"]
    assert body["investigation_summaries"] and body["totals"]["bank_transactions"] == 34 and body["duplicate_groups"]
    csv = client.get(f"/api/report/{run['run_id']}", params={"format": "csv"})
    assert csv.status_code == 200 and csv.headers["content-type"].startswith("text/csv") and csv.text.count("\n") > 10


def test_reupload_resets_run(client, sample_dir):
    rid = _upload(client, sample_dir)
    assert client.post("/api/reconcile", json={"run_id": rid}).status_code == 200
    again = _upload(client, sample_dir, run_id=rid)
    assert again == rid and client.get(f"/api/reconciliation/{rid}").json()["status"] == "ready"
    assert client.get("/api/anomalies", params={"run_id": rid}).json()["total"] == 0


def test_pdf_upload(client, sample_dir):
    pdf = (sample_dir / "bank_statement.pdf").read_bytes()
    r = client.post("/api/upload/bank", files={"file": ("statement.pdf", pdf, "application/pdf")})
    assert r.status_code == 200 and r.json()["transactions_extracted"] == 34 and r.json()["file_type"] == "pdf"


def test_error_responses(client, sample_dir):
    def err(resp, status, code):
        assert resp.status_code == status, resp.text
        assert resp.json()["error"]["code"] == code and "Traceback" not in resp.text and "/home" not in resp.text

    err(client.post("/api/upload/bank", files={"file": ("x.exe", b"MZ", "application/octet-stream")}), 415, "UNSUPPORTED_FILE_TYPE")
    err(client.post("/api/upload/accounting", files={"file": ("x.pdf", b"%PDF-1.4", "application/pdf")}), 415, "UNSUPPORTED_FILE_TYPE")
    err(client.post("/api/upload/bank", files={"file": ("e.csv", b"", "text/csv")}), 400, "EMPTY_FILE")
    err(client.post("/api/upload/bank", files={"file": ("bad.csv", b"foo,bar\n1,2\n", "text/csv")}), 422, "MISSING_COLUMNS")
    err(client.post("/api/upload/bank", files={"file": ("fake.pdf", b"not a pdf", "application/pdf")}), 422, "MALFORMED_FILE")
    err(client.post("/api/upload/bank", files={"file": ("a.csv", b"Date,Debit\nbad,5\n", "text/csv")}), 422, "NO_TRANSACTIONS")
    err(client.post("/api/upload/bank", files={"file": ("a.csv", b"Date,Debit\n2025-01-01,5\n", "text/csv")}, data={"run_id": "missing"}), 404, "RUN_NOT_FOUND")
    err(client.post("/api/upload/bank"), 422, "VALIDATION_ERROR")
    err(client.post("/api/reconcile", json={"run_id": "missing"}), 404, "RUN_NOT_FOUND")
    err(client.post("/api/reconcile", json={}), 422, "VALIDATION_ERROR")
    err(client.get("/api/reconciliation/missing"), 404, "RUN_NOT_FOUND")
    err(client.get("/api/report/missing"), 404, "RUN_NOT_FOUND")
    err(client.get("/api/transactions", params={"limit": 0}), 422, "VALIDATION_ERROR")
    err(client.get("/no/such/route"), 404, "NOT_FOUND")


def test_reconcile_requires_both_files_and_report_needs_completed_run(client, sample_dir):
    r = client.post("/api/upload/bank", files={"file": ("b.csv", (sample_dir / "bank_statement.csv").read_bytes(), "text/csv")}).json()
    resp = client.post("/api/reconcile", json={"run_id": r["run_id"]})
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "RUN_NOT_READY"
    resp = client.get(f"/api/report/{r['run_id']}")
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "RUN_NOT_COMPLETED"
