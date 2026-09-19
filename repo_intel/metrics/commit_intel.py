"""Commit intelligence: activity trends, author breakdown, message stats."""

from __future__ import annotations

from collections import defaultdict

from ..config import ISSUE_PATTERN


def monthly_activity(commits: list[dict]) -> list[dict]:
    """Per-month commits / bug-fixes / churn buckets."""
    buckets: dict[str, dict] = defaultdict(lambda: {"commits": 0, "bugfixes": 0, "churn": 0})
    for c in commits:
        b = buckets[c["date"][:7]]
        b["commits"] += 1
        b["churn"] += c["churn"]
        if c["is_bugfix"]:
            b["bugfixes"] += 1
    return [{"month": m, **v} for m, v in sorted(buckets.items())]


def author_breakdown(authors: dict[str, int], total_commits: int) -> list[dict]:
    rows: list[dict] = [
        {"author": a, "commits": n, "share": round(n / max(total_commits, 1), 3)}
        for a, n in authors.items()
    ]
    rows.sort(key=lambda r: -int(r["commits"]))
    return rows


def commit_summary(commits: list[dict]) -> dict:
    n = len(commits)
    bug = sum(1 for c in commits if c["is_bugfix"])
    linked = sum(1 for c in commits if ISSUE_PATTERN.search(c.get("message", "")))
    linked_bug = sum(
        1 for c in commits if c["is_bugfix"] and ISSUE_PATTERN.search(c.get("message", ""))
    )
    return {
        "commits": n,
        "bugfix_commits": bug,
        "bugfix_ratio": round(bug / n, 3) if n else 0.0,
        "avg_files_per_commit": round(sum(c["files"] for c in commits) / n, 2) if n else 0.0,
        "avg_churn_per_commit": round(sum(c["churn"] for c in commits) / n, 1) if n else 0.0,
        # issue-tracker linkage: distinguishes tracked defects from keyword guesses
        "issue_linked_commits": linked,
        "issue_linked_ratio": round(linked / n, 3) if n else 0.0,
        "tracked_bugfixes": linked_bug,
    }
