"""Tier 4 LLM: caching provider, token budget, provider composition."""

from repo_intel import llm
from repo_intel.llm.base import build_prompt
from repo_intel.llm.caching import CachingProvider, report_signature
from repo_intel.llm.null_provider import NullProvider


def test_caching_provider_hits_cache(report):
    calls = {"n": 0}

    class Counting(NullProvider):
        def summarize(self, rep):
            calls["n"] += 1
            return super().summarize(rep)

    p = CachingProvider(Counting())
    r1 = p.summarize(report)
    r2 = p.summarize(report)
    assert r1["cached"] is False and r2["cached"] is True
    assert calls["n"] == 1  # inner called once despite two summarize() calls


def test_signature_changes_with_health(report):
    sig1 = report_signature(report)
    changed = {**report, "summary": {**report["summary"], "health_score": 1.0}}
    assert report_signature(changed) != sig1


def test_get_provider_wraps_caching():
    assert isinstance(llm.get_provider("none"), CachingProvider)
    assert not isinstance(llm.get_provider("none", cache=False), CachingProvider)


def test_prompt_token_budget():
    big = {
        "summary": {"health_score": 1},
        "release_readiness": {},
        "hotspots": [{"path": "x/" + "a" * 40, "risk_score": 9}] * 300,
        "knowledge_silos": [],
        "flags": [],
    }
    prompt = build_prompt(big, max_chars=500)
    assert len(prompt) <= 560
    assert "truncated" in prompt
