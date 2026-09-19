"""LLMProvider interface + shared rule-based fallback narrative."""

from __future__ import annotations

import abc


class LLMProvider(abc.ABC):
    name = "base"

    @abc.abstractmethod
    def available(self) -> bool:
        """Whether this provider can currently serve requests."""

    @abc.abstractmethod
    def summarize(self, report: dict) -> dict:
        """Return {'text', 'source', 'model'} narrative for a report."""


def rule_based_narrative(report: dict) -> str:
    """Deterministic briefing from metrics only — the no-AI path.

    Shared by NullProvider and used as the fallback when a model call fails.
    """
    s = report.get("summary", {})
    rr = report.get("release_readiness", {})
    pred = report.get("prediction", {})
    lines = []
    hs = s.get("health_score", 0)
    grade = "healthy" if hs >= 70 else "mixed" if hs >= 45 else "at risk"
    lines.append(
        f"Repository health is {grade} ({hs}/100) across {s.get('commits')} commits, "
        f"{s.get('files')} files and {s.get('authors')} authors; "
        f"{s.get('bugfix_commits')} commits were bug fixes."
    )
    hot = report.get("hotspots", [])[:3]
    if hot:
        lines.append(
            "Most bug-prone modules: "
            + ", ".join(f"{h['path']} (risk {h['risk_score']})" for h in hot)
            + "."
        )
    silos = report.get("knowledge_silos", [])[:3]
    if silos:
        lines.append(
            "Knowledge concentration risk in "
            + ", ".join(
                f"{x['path']} ({x['top_author']} {x['top_author_share']:.0%})" for x in silos
            )
            + "."
        )
    lines.append(
        f"Release readiness is {rr.get('score')} ({rr.get('verdict')}): "
        + " ".join(rr.get("reasons", []))
    )
    if pred and pred.get("trend") not in (None, "INSUFFICIENT_DATA"):
        lines.append(f"Trend: defect pressure is {pred['trend'].lower()} ({pred.get('note','')})")
    return " ".join(lines)


def build_prompt(report: dict, max_chars: int | None = None) -> str:
    """Render the briefing prompt, truncated to a rough token budget.

    `max_chars` (default from REPO_INTEL_LLM_MAX_CHARS, else 4000) caps the
    prompt so a huge report can't blow the model's context window. ~4 chars/token.
    """
    import os

    from .prompts import BRIEFING_PROMPT

    if max_chars is None:
        try:
            max_chars = int(os.environ.get("REPO_INTEL_LLM_MAX_CHARS", "4000"))
        except ValueError:
            max_chars = 4000
    s = report.get("summary", {})
    rr = report.get("release_readiness", {})
    hot = "; ".join(f"{h['path']} (risk {h['risk_score']})" for h in report.get("hotspots", [])[:5])
    silos = "; ".join(
        f"{x['path']} {x['top_author_share']:.0%}->{x['top_author']}"
        for x in report.get("knowledge_silos", [])[:5]
    )
    flags = "; ".join(f"[{f['level']}] {f['message']}" for f in report.get("flags", []))
    prompt = BRIEFING_PROMPT.format(
        health=s.get("health_score"),
        commits=s.get("commits"),
        files=s.get("files"),
        authors=s.get("authors"),
        bugfix=s.get("bugfix_commits"),
        readiness=f"{rr.get('score')} ({rr.get('verdict')})",
        hotspots=hot or "none",
        silos=silos or "none",
        flags=flags or "none",
    )
    if max_chars and len(prompt) > max_chars:
        prompt = prompt[:max_chars] + "\n[...truncated for token budget...]"
    return prompt
