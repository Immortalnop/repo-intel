"""Aggregate repository health score (0..100, higher = healthier)."""

from __future__ import annotations

from ..config import DEFAULT, Config


def health_score(
    hotspots: list[dict],
    silos: list[dict],
    readiness: dict,
    file_count: int,
    cfg: Config = DEFAULT,
) -> float:
    n = max(file_count, 1)
    high_risk = sum(1 for h in hotspots if h["risk_score"] >= cfg.hotspot_risk) / n
    silo_ratio = len(silos) / n
    w = cfg.health_weights
    score = (
        w["readiness"] * readiness["score"]
        + w["risk_density"] * (100 - min(high_risk * 300, 100))
        + w["silo_density"] * (100 - min(silo_ratio * 200, 100))
    )
    return round(score, 1)
