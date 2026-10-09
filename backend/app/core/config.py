"""Centralised configuration for AuditFlow AI (env vars / .env file)."""
from __future__ import annotations

import os
from dataclasses import dataclass, fields
from functools import lru_cache
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[2]  # .../backend


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


@dataclass
class Settings:
    app_name: str = "AuditFlow AI"
    tagline: str = "Reconcile. Investigate. Resolve."
    version: str = "1.0.0"

    database_url: str = "sqlite:///./auditflow.db"
    upload_dir: str = str(BASE_DIR / "uploads")
    reports_dir: str = str(BASE_DIR / "reports")
    max_upload_mb: int = 20
    cors_origins: str = "*"
    log_level: str = "INFO"

    # Ollama (optional local LLM)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = ""
    ollama_timeout_seconds: float = 90.0
    ollama_check_timeout_seconds: float = 1.5
    llm_max_explanations: int = 25  # max LLM explanations per reconciliation run

    # Thresholds / tolerances
    high_value_threshold: float = 100000.0
    strict_date_tolerance_days: int = 1
    relaxed_date_tolerance_days: int = 3
    strict_amount_tolerance_pct: float = 0.0
    relaxed_amount_tolerance_pct: float = 25.0
    amount_epsilon: float = 0.01
    amount_partial_credit: float = 0.4  # share of amount points when amount only within relaxed tolerance
    description_candidate_threshold: float = 70.0
    description_min_for_likely: float = 40.0  # below this (and no reference match) score is capped at REVIEW
    description_search_window_days: int = 30
    duplicate_min_confidence: float = 0.7
    suspicious_min_indicators: int = 2

    # Classification thresholds
    match_threshold: float = 90.0
    likely_match_threshold: float = 75.0
    review_threshold: float = 50.0

    # Score weights
    amount_score_weight: float = 40.0
    date_score_weight: float = 20.0
    description_score_weight: float = 20.0
    reference_score_weight: float = 20.0

    @classmethod
    def from_env(cls) -> "Settings":
        _load_dotenv(BASE_DIR / ".env")
        kwargs: dict[str, Any] = {}
        types = {"int": int, "float": float, "str": str}
        for f in fields(cls):
            raw = os.environ.get(f.name.upper())
            if raw is None or raw == "":
                continue
            typ = types[f.type] if isinstance(f.type, str) else f.type
            try:
                kwargs[f.name] = typ(raw)
            except ValueError:
                raise ValueError(f"Invalid value for {f.name.upper()}: {raw!r}")
        return cls(**kwargs)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()


def reload_settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()
