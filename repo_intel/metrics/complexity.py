"""Multi-language cyclomatic complexity of current source, via lizard (optional).

lizard analyzes ~27 languages (Python, JS/TS, Java, Go, Rust, C/C++, Ruby, PHP,
Kotlin, Swift, Scala, …) by file extension. Complements the history-based signals
with a static view of today's code. If lizard is not installed, this degrades to
an empty result and the rest of the report is unaffected.
"""

from __future__ import annotations

import os

from ..logging_utils import get_logger

log = get_logger("metrics.complexity")

try:
    import lizard

    _HAVE_LIZARD = True
except Exception:  # pragma: no cover
    _HAVE_LIZARD = False


def available() -> bool:
    return _HAVE_LIZARD


def sample_commits(commits: list[dict], points: int = 8) -> list[dict]:
    """Pick up to `points` commits evenly across chronological history."""
    if not commits or points <= 0:
        return []
    ordered = sorted(commits, key=lambda c: c["timestamp"])
    if len(ordered) <= points:
        return ordered
    step = (len(ordered) - 1) / (points - 1)
    idx = sorted({round(i * step) for i in range(points)})
    return [ordered[i] for i in idx]


def complexity_trend(
    repo_path: str, commits: list[dict], points: int = 8, max_files: int = 300
) -> list[dict]:
    """Mean cyclomatic complexity of the source tree at sampled commits.

    Reads file blobs directly from each commit's tree (no checkout), so it tracks
    how complexity evolves over history the way churn does. Bounded by `points`
    (time samples) and `max_files` (files per sample). Empty if lizard is absent.
    """
    if not _HAVE_LIZARD:
        return []
    try:
        from git import Repo
    except Exception:  # pragma: no cover
        return []
    repo = Repo(repo_path, search_parent_directories=True)
    series: list[dict] = []
    for c in sample_commits(commits, points):
        try:
            commit = repo.commit(c["hash"])
        except Exception:
            continue
        scores: list[int] = []
        nfiles = 0
        for blob in commit.tree.traverse():
            if getattr(blob, "type", None) != "blob":
                continue
            if lizard.get_reader_for(blob.path) is None:
                continue
            try:
                code = blob.data_stream.read().decode("utf-8", "ignore")
                info = lizard.analyze_file.analyze_source_code(blob.path, code)
            except Exception:
                continue
            scores.extend(f.cyclomatic_complexity for f in info.function_list)
            nfiles += 1
            if nfiles >= max_files:
                break
        if scores:
            series.append(
                {
                    "commit": c["hash"][:10],
                    "date": c["date"],
                    "avg_complexity": round(sum(scores) / len(scores), 2),
                    "functions": len(scores),
                    "files": nfiles,
                }
            )
    log.info("complexity trend: %d sample points", len(series))
    return series


def file_complexity(repo_path: str, paths: list[str]) -> dict[str, dict]:
    """Return {path: {avg, max, functions, language}} cyclomatic complexity.

    Reads the current working-tree contents. Files whose extension no lizard
    language reader recognizes, and unreadable files, are skipped. Empty dict
    when lizard is unavailable.
    """
    if not _HAVE_LIZARD:
        return {}
    out: dict[str, dict] = {}
    for rel in paths:
        full = os.path.join(repo_path, rel)
        if not os.path.isfile(full):
            continue
        reader = lizard.get_reader_for(full)
        if reader is None:  # extension not supported by any language reader
            continue
        try:
            info = lizard.analyze_file(full)
        except Exception:  # unparseable source, encoding issues, etc.
            continue
        funcs = info.function_list
        if not funcs:
            continue
        scores = [f.cyclomatic_complexity for f in funcs]
        out[rel] = {
            "avg": round(sum(scores) / len(scores), 1),
            "max": max(scores),
            "functions": len(scores),
            "language": getattr(reader, "language_names", ["?"])[0],
        }
    log.info("computed complexity for %d files", len(out))
    return out
