from app.llm.ollama_client import OllamaClient


def test_health_ok_without_ollama(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy" and body["database"] == "connected"
    assert body["ollama"] == "unavailable"
    assert body["tagline"] == "Reconcile. Investigate. Resolve."


def test_health_reports_ollama_available(client, monkeypatch):
    monkeypatch.setattr(OllamaClient, "is_available", lambda self, force=False: True)
    assert client.get("/health").json()["ollama"] == "available"


def test_ollama_detection_unreachable(settings):
    settings.ollama_base_url = "http://127.0.0.1:9"
    assert OllamaClient(settings).is_available(force=True) is False
