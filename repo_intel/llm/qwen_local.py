"""Local Qwen provider. Talks to a self-hosted endpoint — nothing leaves the box.

Backends (auto-detected):
  ollama : {url}/api/generate            (default; `ollama run qwen2.5:3b-instruct`)
  openai : {url}/v1/chat/completions      (LM Studio / vLLM / llama.cpp server)

Env:
  REPO_INTEL_LLM_BACKEND  ollama|openai|auto   (default auto)
  REPO_INTEL_LLM_URL      base url
  REPO_INTEL_LLM_MODEL    model name (default qwen2.5:3b-instruct)

Falls back to the rule-based narrative if the model call fails.
"""

from __future__ import annotations

import os

import requests

from .base import LLMProvider, build_prompt, rule_based_narrative

OLLAMA_URL = "http://localhost:11434"
OPENAI_URL = "http://localhost:1234"
DEFAULT_MODEL = "qwen2.5:3b-instruct"


class QwenLocalProvider(LLMProvider):
    name = "qwen_local"

    def __init__(self):
        self.backend_pref = os.environ.get("REPO_INTEL_LLM_BACKEND", "auto").lower()
        self.model = os.environ.get("REPO_INTEL_LLM_MODEL", DEFAULT_MODEL)

    def _url(self, backend: str) -> str:
        default = OLLAMA_URL if backend == "ollama" else OPENAI_URL
        return os.environ.get("REPO_INTEL_LLM_URL", default).rstrip("/")

    def _detect(self, timeout: float = 1.5):
        cands = (
            [self.backend_pref]
            if self.backend_pref in ("ollama", "openai")
            else ["ollama", "openai"]
        )
        for b in cands:
            try:
                probe = "/api/tags" if b == "ollama" else "/v1/models"
                if requests.get(self._url(b) + probe, timeout=timeout).status_code == 200:
                    return b
            except Exception:
                continue
        return None

    def available(self) -> bool:
        return self._detect() is not None

    def summarize(self, report: dict) -> dict:
        backend = self._detect()
        if backend is None:
            return {"text": rule_based_narrative(report), "source": "fallback", "model": None}
        prompt = build_prompt(report)
        try:
            text = self._call_ollama(prompt) if backend == "ollama" else self._call_openai(prompt)
            return {"text": text.strip(), "source": f"llm:{backend}", "model": self.model}
        except Exception as exc:
            return {
                "text": rule_based_narrative(report),
                "source": "fallback",
                "model": None,
                "error": str(exc),
            }

    def _call_ollama(self, prompt: str, timeout: float = 60.0) -> str:
        r = requests.post(
            self._url("ollama") + "/api/generate",
            json={"model": self.model, "prompt": prompt, "stream": False},
            timeout=timeout,
        )
        r.raise_for_status()
        return r.json().get("response", "")

    def _call_openai(self, prompt: str, timeout: float = 60.0) -> str:
        r = requests.post(
            self._url("openai") + "/v1/chat/completions",
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
            },
            timeout=timeout,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
