"""A provider decorator that caches narratives by report signature.

Wraps any LLMProvider (Null, Qwen, or a future one) and returns a cached result
when asked to summarize a report it has already seen — avoiding repeat model
calls for an unchanged report. Demonstrates that the LLMProvider interface
composes.
"""

from __future__ import annotations

import hashlib
import json

from .base import LLMProvider


def report_signature(report: dict) -> str:
    """Stable hash of the parts of a report a narrative depends on."""
    sig = {
        "health": report.get("summary", {}).get("health_score"),
        "readiness": report.get("release_readiness", {}).get("score"),
        "hotspots": [(h["path"], h["risk_score"]) for h in report.get("hotspots", [])[:10]],
        "silos": [(s["path"], s["top_author"]) for s in report.get("knowledge_silos", [])[:10]],
        "flags": [f["code"] for f in report.get("flags", [])],
    }
    raw = json.dumps(sig, sort_keys=True, default=str)
    return hashlib.sha1(raw.encode()).hexdigest()


class CachingProvider(LLMProvider):
    name = "caching"

    def __init__(self, inner: LLMProvider, max_entries: int = 64):
        self.inner = inner
        self.max_entries = max_entries
        self._cache: dict[str, dict] = {}

    def available(self) -> bool:
        return self.inner.available()

    def summarize(self, report: dict) -> dict:
        key = report_signature(report)
        if key in self._cache:
            return {**self._cache[key], "cached": True}
        result = self.inner.summarize(report)
        if len(self._cache) >= self.max_entries:
            self._cache.pop(next(iter(self._cache)))  # drop oldest
        self._cache[key] = result
        return {**result, "cached": False}
