"""Code ownership & bus factor."""

from __future__ import annotations

from ..config import DEFAULT


def ownership_share(author_commits: dict[str, int]) -> tuple[str, float]:
    """(top_author, share 0..1 of that file's commits)."""
    total = sum(author_commits.values())
    if total == 0:
        return ("", 0.0)
    top, n = max(author_commits.items(), key=lambda kv: kv[1])
    return (top, n / total)


def bus_factor(author_commits: dict[str, int], threshold: float | None = None) -> int:
    """Min authors whose combined commits reach `threshold` of the total.

    1 = a single person holds the majority of the knowledge.
    """
    th = threshold if threshold is not None else DEFAULT.bus_factor_threshold
    total = sum(author_commits.values())
    if total == 0:
        return 0
    cum, factor = 0, 0
    for _, n in sorted(author_commits.items(), key=lambda kv: -kv[1]):
        cum += n
        factor += 1
        if cum / total >= th:
            break
    return factor
