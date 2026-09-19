"""Default no-op provider: deterministic rule-based narrative, no AI."""

from __future__ import annotations

from .base import LLMProvider, rule_based_narrative


class NullProvider(LLMProvider):
    name = "null"

    def available(self) -> bool:
        return True  # always works — it's just metrics

    def summarize(self, report: dict) -> dict:
        return {"text": rule_based_narrative(report), "source": "fallback", "model": None}
