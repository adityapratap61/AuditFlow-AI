"""LLM explanation with strict validation and deterministic fallback."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import Settings
from app.llm.fallback import fallback_explanation, fallback_summary
from app.llm.ollama_client import OllamaClient, OllamaError
from app.llm.prompts import SYSTEM_PROMPT, build_explanation_prompt, build_summary_prompt

log = logging.getLogger(__name__)
_NUM = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?(?![\w])")
_FRAUD = re.compile(r"(?i)(confirmed|definite(ly)?|proven|certain(ly)?|clearly|undoubtedly)\W+(\w+\W+){0,3}fraud|"
                    r"\b(is|are|was|were)\s+(a\s+)?fraud(ulent)?\b|\bcommitted\s+fraud\b")


def _canon(tok: str) -> Optional[str]:
    try:
        return f"{float(tok.replace(',', '')):.2f}"
    except ValueError:
        return None


def _numbers(text: str) -> set:
    out = set()
    for tok in _NUM.findall(text):
        digits = re.sub(r"\D", "", tok)
        if len(digits) >= 3:
            c = _canon(tok)
            if c:
                out.add(c)
    return out


def validate_explanation(data: Dict[str, Any], evidence: Dict[str, Any]) -> Dict[str, Any]:
    """Raises ValueError if the LLM output is malformed or states facts not present in the evidence."""
    if not isinstance(data.get("explanation"), str) or len(data["explanation"].strip()) < 20:
        raise ValueError("missing explanation")
    for key in ("inference", "recommended_action"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError(f"missing {key}")
    pts = data.get("evidence_points", [])
    if not isinstance(pts, list) or not all(isinstance(p, str) for p in pts):
        raise ValueError("invalid evidence_points")
    blob = " ".join([data["explanation"], data["inference"], data["recommended_action"], *pts])
    if _FRAUD.search(blob):
        raise ValueError("asserts fraud")
    allowed = _numbers(json.dumps(evidence, default=str))
    unknown = _numbers(blob) - allowed
    if unknown:
        raise ValueError(f"numbers not in evidence: {sorted(unknown)[:3]}")
    return {"explanation": data["explanation"].strip(), "evidence_points": pts, "inference": data["inference"].strip(),
            "recommended_action": data["recommended_action"].strip(), "source": "ollama"}


class Explainer:
    """Wraps OllamaClient; always returns a usable explanation."""

    def __init__(self, settings: Settings, client: Optional[OllamaClient] = None, use_llm: bool = True,
                 max_calls: Optional[int] = None):
        self.s = settings
        self.client = client or OllamaClient(settings)
        self.use_llm = use_llm
        self.remaining = self.s.llm_max_explanations if max_calls is None else max_calls

    def _llm_ok(self) -> bool:
        return self.use_llm and self.remaining > 0 and self.client.is_available()

    def explain(self, evidence: Dict[str, Any], flags: Optional[List[str]] = None) -> Dict[str, Any]:
        flags = flags or []
        base = fallback_explanation(evidence, flags)
        if not self._llm_ok():
            return base
        self.remaining -= 1
        try:
            raw = self.client.generate_json(build_explanation_prompt(evidence, flags), SYSTEM_PROMPT)
            out = validate_explanation(raw, evidence)
            if "POTENTIALLY_SUSPICIOUS" in flags and "manual verification" not in out["explanation"].lower():
                out["explanation"] += " Potentially suspicious transaction requiring manual verification."
            return out
        except (OllamaError, ValueError) as exc:
            log.warning("LLM explanation rejected, using fallback: %s", exc)
            return base

    def summarize(self, summary: Dict[str, Any]) -> Tuple[str, str]:
        base = fallback_summary(summary)
        if not self._llm_ok():
            return base, "fallback"
        try:
            data = self.client.generate_json(build_summary_prompt(summary), SYSTEM_PROMPT)
            text = data.get("summary")
            if not isinstance(text, str) or len(text) < 20 or _FRAUD.search(text):
                raise ValueError("invalid summary")
            if _numbers(text) - _numbers(json.dumps(summary, default=str)):
                raise ValueError("numbers not in summary")
            return text.strip(), "ollama"
        except (OllamaError, ValueError) as exc:
            log.warning("LLM summary rejected, using fallback: %s", exc)
            return base, "fallback"
