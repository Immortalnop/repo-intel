"""LLM layer: null provider, availability, fallback, and a mocked Qwen call."""

from repo_intel import llm as llm_pkg
from repo_intel.llm import base, qwen_local
from repo_intel.llm.null_provider import NullProvider


def test_null_provider_always_available(report):
    p = NullProvider()
    assert p.available()
    res = p.summarize(report)
    assert res["source"] == "fallback" and res["text"]


def test_rule_based_narrative_mentions_hotspot(report):
    text = base.rule_based_narrative(report)
    assert "core/engine.py" in text
    assert "health" in text.lower()


def test_get_provider_none(report):
    p = llm_pkg.get_provider("none", cache=False)
    assert isinstance(p, NullProvider)


def test_qwen_unavailable_falls_back(report, monkeypatch):
    # no server: detection returns None -> fallback
    monkeypatch.setattr(qwen_local.QwenLocalProvider, "_detect", lambda self, timeout=1.5: None)
    res = qwen_local.QwenLocalProvider().summarize(report)
    assert res["source"] == "fallback"


def test_qwen_mocked_ollama(report, monkeypatch):
    prov = qwen_local.QwenLocalProvider()
    monkeypatch.setattr(prov, "_detect", lambda timeout=1.5: "ollama")

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"response": "Health looks fine. Ship it."}

    monkeypatch.setattr(qwen_local.requests, "post", lambda *a, **k: FakeResp())
    res = prov.summarize(report)
    assert res["source"] == "llm:ollama"
    assert "Ship it" in res["text"]


def test_qwen_call_error_falls_back(report, monkeypatch):
    prov = qwen_local.QwenLocalProvider()
    monkeypatch.setattr(prov, "_detect", lambda timeout=1.5: "ollama")

    def boom(*a, **k):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(qwen_local.requests, "post", boom)
    res = prov.summarize(report)
    assert res["source"] == "fallback"
    assert "error" in res
