"""Release readiness scoring for a recent window."""

from __future__ import annotations

from datetime import datetime

from ..config import DEFAULT, Config


def release_readiness(
    commits: list[dict],
    hotspots: list[dict],
    now: datetime,
    cfg: Config = DEFAULT,
) -> dict:
    """Score 0..100 (higher = safer). Penalizes rising bug-fix rate,
    active high-risk hotspots and high recent churn.
    """
    window_days = cfg.readiness_window_days
    cutoff = now.timestamp() - window_days * 86400
    window = [c for c in commits if c["timestamp"] >= cutoff]
    n = len(window)
    if n == 0:
        return {
            "score": 50.0,
            "verdict": "UNKNOWN",
            "window_days": window_days,
            "commits_in_window": 0,
            "reasons": ["No commits in the recent window."],
        }

    bugfix_rate = sum(1 for c in window if c["is_bugfix"]) / n
    avg_churn = sum(c["churn"] for c in window) / n
    active_hot = [h for h in hotspots if h["recency"] > 0.5 and h["risk_score"] >= 50]

    score, reasons = 100.0, []
    p_bug = min(bugfix_rate * 80, 45)
    score -= p_bug
    reasons.append(f"Bug-fix rate {bugfix_rate:.0%} of recent commits (-{p_bug:.0f}).")
    p_hot = min(len(active_hot) * 6, 30)
    score -= p_hot
    reasons.append(f"{len(active_hot)} active high-risk hotspot(s) (-{p_hot:.0f}).")
    p_churn = min(avg_churn / 50.0, 1.0) * 20
    score -= p_churn
    reasons.append(f"Avg churn {avg_churn:.0f} lines/commit (-{p_churn:.0f}).")

    score = max(0.0, round(score, 1))
    verdict = "READY" if score >= 70 else "CAUTION" if score >= 45 else "NOT READY"
    return {
        "score": score,
        "verdict": verdict,
        "window_days": window_days,
        "commits_in_window": n,
        "bugfix_rate": round(bugfix_rate, 3),
        "avg_churn": round(avg_churn, 1),
        "active_hotspots": len(active_hot),
        "reasons": reasons,
    }
