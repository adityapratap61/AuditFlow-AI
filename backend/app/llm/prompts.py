"""Prompts for the local LLM. The model only phrases explanations from supplied facts."""
import json

SYSTEM_PROMPT = (
    "You are the explanation writer of AuditFlow AI, a bank reconciliation assistant. "
    "Rules: use ONLY the facts in the supplied JSON evidence. Never invent or recalculate transactions, amounts, dates, "
    "references or vendors; copy numbers exactly as given. Distinguish evidence (what the data shows) from inference "
    "(what it probably means). Never state that fraud is confirmed; for unusual items say 'potentially suspicious and "
    "requiring manual verification'. Recommend manual verification when uncertain. Reply with JSON only."
)

EXPLAIN_SCHEMA = ('{"explanation": "2-4 sentences", "evidence_points": ["short factual bullet", "..."], '
                  '"inference": "one sentence", "recommended_action": "one sentence"}')


def build_explanation_prompt(evidence: dict, flags: list) -> str:
    return (f"Explain this reconciliation finding for an accountant.\nFlags: {json.dumps(flags)}\n"
            f"Evidence (JSON):\n{json.dumps(evidence, indent=2, default=str)}\n\n"
            f"Respond with ONLY a JSON object of this shape: {EXPLAIN_SCHEMA}")


def build_summary_prompt(summary: dict) -> str:
    return (f"Write a 3-5 sentence reconciliation summary for management using only these figures.\n"
            f"Summary (JSON):\n{json.dumps(summary, indent=2, default=str)}\n\n"
            'Respond with ONLY a JSON object: {"summary": "..."}')
