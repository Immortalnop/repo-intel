"""Developer knowledge concentration (bus-factor risk at file & project level)."""

from __future__ import annotations

from ..config import DEFAULT, Config
from . import ownership as own_m


def knowledge_silos(file_rows: list[dict], cfg: Config = DEFAULT) -> list[dict]:
    """Files whose ownership is concentrated in a single author."""
    silos = [
        r
        for r in file_rows
        if r["top_author_share"] >= cfg.silo_owner_share and r["commits"] >= cfg.silo_min_commits
    ]
    silos.sort(key=lambda r: (-r["top_author_share"], -r["commits"]))
    return silos


def project_concentration(authors: dict[str, int]) -> dict:
    """Overall project bus-factor picture across all commits."""
    top, share = own_m.ownership_share(authors)
    return {
        "top_author": top,
        "top_author_share": round(share, 3),
        "bus_factor": own_m.bus_factor(authors),
        "author_count": len(authors),
    }


def departure_risk(file_rows: list[dict], cfg: Config = DEFAULT) -> list[dict]:
    """Per-author "truck factor": how much knowledge leaves if they do.

    For each author, count the files they solely dominate (silo owner) and the
    share of the codebase those represent. High values flag single points of
    failure in the team's knowledge.
    """
    total_files = max(len(file_rows), 1)
    owned: dict[str, dict] = {}
    for r in file_rows:
        if r["top_author_share"] >= cfg.silo_owner_share and r["commits"] >= cfg.silo_min_commits:
            a = r["top_author"]
            e = owned.setdefault(a, {"author": a, "owned_files": 0, "files": []})
            e["owned_files"] += 1
            e["files"].append(r["path"])
    rows = [
        {
            "author": e["author"],
            "owned_files": e["owned_files"],
            "codebase_share": round(e["owned_files"] / total_files, 3),
            "files": e["files"][:10],
        }
        for e in owned.values()
    ]
    rows.sort(key=lambda r: -int(r["owned_files"]))
    return rows
