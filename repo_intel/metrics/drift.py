"""Architectural drift via temporal coupling (co-change analysis)."""

from __future__ import annotations

from ..config import DEFAULT, Config


def _top_dir(path: str) -> str:
    return path.split("/", 1)[0] if "/" in path else "."


def temporal_coupling(
    cochange: dict[tuple[str, str], int],
    file_commits: dict[str, int],
    cfg: Config = DEFAULT,
) -> list[dict]:
    """Files that change together too often.

    confidence = max(P(B|A), P(A|B)). Cross-module high coupling signals
    architectural erosion / drift.
    """
    out: list[dict] = []
    for (a, b), shared in cochange.items():
        if shared < cfg.coupling_min_shared:
            continue
        ca, cb = file_commits.get(a, 0), file_commits.get(b, 0)
        if ca == 0 or cb == 0:
            continue
        conf = max(shared / ca, shared / cb)
        if conf < cfg.coupling_min_confidence:
            continue
        out.append(
            {
                "file_a": a,
                "file_b": b,
                "shared_changes": shared,
                "confidence": round(conf, 2),
                "cross_module": _top_dir(a) != _top_dir(b),
            }
        )
    out.sort(key=lambda d: (-int(d["shared_changes"]), -float(d["confidence"])))
    return out
