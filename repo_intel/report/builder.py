"""Unified result object: mine -> metrics -> analysis -> one report dict.

This is the orchestration seam every surface (CLI, API, exporters) consumes.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..analysis import flags as flags_m
from ..analysis import predict as predict_m
from ..analysis.health_score import health_score as compute_health
from ..config import DEFAULT, Config
from ..errors import EmptyRepositoryError
from ..extract import driller, git_loader
from ..extract.driller import History
from ..metrics import bugproneness, commit_intel, complexity, drift, knowledge, ownership, release
from ..metrics import churn as churn_m


def build_report(
    history: History, top: int = 20, cfg: Config = DEFAULT, complexity_trend: bool = False
) -> dict:
    if not history.files:
        return {"error": "No commits/files mined.", "repo": history.repo}

    now = datetime.now(timezone.utc)
    max_churn = churn_m.max_churn(history)

    file_rows: list[dict] = []
    for f in history.files.values():
        score, signals = bugproneness.file_risk_score(
            f.churn, f.commits, f.bugfixes, f.last_seen, f.authors, max_churn, now, cfg
        )
        top_author, share = ownership.ownership_share(f.authors)
        file_rows.append(
            {
                "path": f.path,
                "commits": f.commits,
                "insertions": f.insertions,
                "deletions": f.deletions,
                "churn": f.churn,
                "bugfixes": f.bugfixes,
                "bugfix_ratio": round(f.bugfixes / f.commits, 3) if f.commits else 0,
                "authors": len(f.authors),
                "top_author": top_author,
                "top_author_share": round(share, 3),
                "bus_factor": ownership.bus_factor(f.authors),
                "risk_score": score,
                "recency": round(
                    churn_m.recency_weight(f.last_seen, now, cfg.recency_half_life_days), 3
                ),
                "signals": signals,
                "last_seen": f.last_seen.isoformat() if f.last_seen else None,
            }
        )

    # static complexity of current source (radon; no-op if unavailable)
    cx = complexity.file_complexity(history.repo, list(history.files.keys()))
    for r in file_rows:
        c = cx.get(r["path"])
        if c:
            r["complexity"] = c["avg"]
            r["complexity_max"] = c["max"]
            r["complexity_language"] = c["language"]

    cx_trend = (
        complexity.complexity_trend(history.repo, history.commits) if complexity_trend else []
    )

    hotspots = sorted(file_rows, key=lambda r: -float(r["risk_score"]))
    coupling = drift.temporal_coupling(history.cochange, history.file_commits(), cfg)
    readiness = release.release_readiness(history.commits, hotspots, now, cfg)
    silos = knowledge.knowledge_silos(file_rows, cfg)
    departures = knowledge.departure_risk(file_rows, cfg)
    authors = commit_intel.author_breakdown(history.authors, len(history.commits))
    activity = commit_intel.monthly_activity(history.commits)
    prediction = predict_m.predict_risk(activity)
    flags = flags_m.raise_flags(hotspots, silos, coupling, readiness, authors, cfg)
    hscore = compute_health(hotspots, silos, readiness, len(history.files), cfg)
    csum = commit_intel.commit_summary(history.commits)
    info = git_loader.load_repo_info(history.repo)

    return {
        "repo": history.repo,
        "generated_at": now.isoformat(),
        "git": {
            "active_branch": info.active_branch,
            "head": info.head,
            "branches": len(info.branches),
            "tags": len(info.tags),
            "latest_tag": info.tags[-1] if info.tags else None,
        },
        "summary": {
            "commits": len(history.commits),
            "files": len(history.files),
            "authors": len(history.authors),
            "bugfix_commits": csum["bugfix_commits"],
            "total_churn": sum(f.churn for f in history.files.values()),
            "avg_churn_per_commit": csum["avg_churn_per_commit"],
            "first_commit": min((c["date"] for c in history.commits), default=None),
            "last_commit": max((c["date"] for c in history.commits), default=None),
            "health_score": hscore,
            "issue_linked_ratio": csum["issue_linked_ratio"],
            "tracked_bugfixes": csum["tracked_bugfixes"],
            "complexity_available": complexity.available(),
        },
        "release_readiness": readiness,
        "prediction": prediction,
        "hotspots": hotspots[:top],
        "knowledge_silos": silos[:top],
        "departure_risk": departures[:top],
        "coupling": coupling[:top],
        "authors": authors,
        "commit_activity": activity,
        "complexity_trend": cx_trend,
        "flags": flags,
        "all_files": file_rows,
    }


def analyze(
    path: str,
    since: datetime | None = None,
    branch: str | None = None,
    max_commits: int | None = None,
    top: int = 20,
    use_cache: bool = False,
    incremental: bool = False,
    jobs: int = 1,
    timeout: float | None = None,
    validate: bool = False,
    complexity_trend: bool = False,
    cfg: Config = DEFAULT,
) -> dict:
    """Mine and build the full report dict.

    - use_cache: read/write a sqlite cache of the mined history.
    - incremental: extend the cached history with only new commits (implies cache).
    - jobs: mine with N worker processes (parallel), when >1.
    - timeout: abort mining after this many seconds (MiningTimeoutError).
    - validate: check the result against the Pydantic `Report` schema.
    - complexity_trend: also compute complexity over sampled history (slower).

    Raises EmptyRepositoryError if the repo (or selected range) has no commits.
    """
    history = _mine(path, since, branch, max_commits, use_cache, incremental, jobs, timeout, cfg)
    if not history.commits:
        raise EmptyRepositoryError(f"{path} has no commits in the selected range.")
    report = build_report(history, top=top, cfg=cfg, complexity_trend=complexity_trend)
    if validate and "error" not in report:
        from ..models import Report

        Report.model_validate(report)  # raises on schema violation
    return report


def _mine(path, since, branch, max_commits, use_cache, incremental, jobs, timeout, cfg):
    from ..extract import cache

    if incremental:
        cached = cache.load(path, since, branch, max_commits)
        if cached is not None:
            from ..extract.mine import drill_incremental

            history = drill_incremental(path, cached, branch=branch, cfg=cfg)
            cache.save(history, since, branch, max_commits)
            return history

    if use_cache:
        cached = cache.load(path, since, branch, max_commits)
        if cached is not None:
            return cached

    if jobs > 1 and since is None and max_commits is None:
        from ..extract.mine import drill_parallel

        history = drill_parallel(path, jobs=jobs, branch=branch, cfg=cfg)
    else:
        history = driller.drill(
            path, since=since, branch=branch, max_commits=max_commits, timeout=timeout, cfg=cfg
        )
    if use_cache or incremental:
        cache.save(history, since, branch, max_commits)
    return history
