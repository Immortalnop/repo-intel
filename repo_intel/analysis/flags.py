"""Rule engine: turn metrics into prioritized risk flags."""

from __future__ import annotations

from ..config import DEFAULT, Config


def raise_flags(
    hotspots: list[dict],
    silos: list[dict],
    coupling: list[dict],
    readiness: dict,
    authors: list[dict],
    cfg: Config = DEFAULT,
) -> list[dict]:
    flags: list[dict] = []

    def add(level, code, msg):
        flags.append({"level": level, "code": code, "message": msg})

    for h in hotspots[:5]:
        if h["risk_score"] >= cfg.hotspot_risk:
            add(
                "high",
                "BUG_PRONE_MODULE",
                f"{h['path']} risk {h['risk_score']} "
                f"(churn {h['churn']}, {h['bugfixes']} fixes).",
            )
    for s in silos[:5]:
        add(
            "medium",
            "KNOWLEDGE_SILO",
            f"{s['path']} is {s['top_author_share']:.0%} owned by "
            f"{s['top_author']} (bus factor {s['bus_factor']}).",
        )
    for c in coupling[:5]:
        if c["cross_module"]:
            add(
                "medium",
                "ARCHITECTURAL_DRIFT",
                f"{c['file_a']} <-> {c['file_b']} co-change "
                f"{c['shared_changes']}x across modules (conf {c['confidence']:.0%}).",
            )
    if readiness["verdict"] in ("NOT READY", "CAUTION"):
        add(
            "high" if readiness["verdict"] == "NOT READY" else "medium",
            "RELEASE_RISK",
            f"Release readiness {readiness['score']} — {readiness['verdict']}.",
        )
    if authors and authors[0]["share"] >= cfg.project_bus_factor_share:
        add(
            "medium",
            "PROJECT_BUS_FACTOR",
            f"{authors[0]['author']} authored {authors[0]['share']:.0%} of all commits.",
        )
    if not flags:
        add("info", "OK", "No significant risks detected.")
    return flags
