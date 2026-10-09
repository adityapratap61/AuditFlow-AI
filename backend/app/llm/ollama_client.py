"""Minimal Ollama client (optional). Every failure degrades gracefully - callers must handle OllamaError."""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, Optional

from app.core.config import Settings

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None

log = logging.getLogger(__name__)


class OllamaError(Exception):
    pass


class OllamaClient:
    def __init__(self, settings: Settings):
        self.s = settings
        self._avail: Optional[bool] = None
        self._checked_at = 0.0
        self._model: Optional[str] = settings.ollama_model or None

    @property
    def base_url(self) -> str:
        return self.s.ollama_base_url.rstrip("/")

    def is_available(self, force: bool = False) -> bool:
        if not force and self._avail is not None and time.time() - self._checked_at < 15:
            return self._avail
        ok = False
        if httpx is not None:
            try:
                r = httpx.get(f"{self.base_url}/api/tags", timeout=self.s.ollama_check_timeout_seconds)
                if r.status_code == 200:
                    models = [m.get("name") for m in r.json().get("models", [])]
                    if not self._model and models:
                        self._model = models[0]
                    ok = bool(self._model) and (not models or any(
                        m == self._model or (m or "").split(":")[0] == self._model.split(":")[0] for m in models))
            except Exception as exc:  # connection refused, timeout, bad JSON ...
                log.info("Ollama unavailable (%s)", type(exc).__name__)
        self._avail, self._checked_at = ok, time.time()
        log.info("Ollama availability: %s", "available" if ok else "unavailable")
        return ok

    def generate(self, prompt: str, system: Optional[str] = None, as_json: bool = True) -> str:
        if httpx is None or not self.is_available():
            raise OllamaError("Ollama is not available")
        payload: Dict[str, Any] = {"model": self._model, "prompt": prompt, "stream": False,
                                   "options": {"temperature": 0.1}}
        if system:
            payload["system"] = system
        if as_json:
            payload["format"] = "json"
        try:
            r = httpx.post(f"{self.base_url}/api/generate", json=payload, timeout=self.s.ollama_timeout_seconds)
            r.raise_for_status()
            return r.json().get("response", "")
        except Exception as exc:
            self._avail = False
            raise OllamaError(f"Ollama request failed ({type(exc).__name__})")

    def generate_json(self, prompt: str, system: Optional[str] = None) -> Dict[str, Any]:
        text = self.generate(prompt, system, as_json=True)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if not m:
                raise OllamaError("LLM returned non-JSON output")
            try:
                data = json.loads(m.group(0))
            except json.JSONDecodeError:
                raise OllamaError("LLM returned invalid JSON")
        if not isinstance(data, dict):
            raise OllamaError("LLM JSON is not an object")
        return data


_client: Optional[OllamaClient] = None


def get_ollama_client() -> OllamaClient:
    """Process-wide client (keeps the short availability cache). Tests may monkeypatch OllamaClient methods."""
    global _client
    from app.core.config import get_settings
    if _client is None:
        _client = OllamaClient(get_settings())
    return _client


def reset_ollama_client() -> None:
    global _client
    _client = None
