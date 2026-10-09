import os
import sys
import tempfile
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
_tmp = tempfile.mkdtemp(prefix="auditflow_test_")
os.environ.update({  # must be set before app modules read settings; tests never need a real Ollama
    "DATABASE_URL": "sqlite://", "UPLOAD_DIR": os.path.join(_tmp, "uploads"), "REPORTS_DIR": os.path.join(_tmp, "reports"),
    "OLLAMA_BASE_URL": "http://127.0.0.1:9", "OLLAMA_MODEL": "test-model", "LOG_LEVEL": "WARNING"})


@pytest.fixture
def settings():
    from app.core.config import Settings
    return Settings()  # pristine defaults, independent of any local .env


@pytest.fixture(scope="session")
def sample_dir():
    return BACKEND / "sample_data"


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c
