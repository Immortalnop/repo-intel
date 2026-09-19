"""PyDriller layer: traverse commit/file history into structured records.

Produces a `History` object — the single source of truth all metrics consume.
No scoring happens here, only extraction. Hardened against binary files, merge
commits, giant commits, non-git paths, and long-running mines (timeout).
"""

from __future__ import annotations

import fnmatch
import itertools
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..config import BUGFIX_PATTERN as _BUGFIX
from ..config import DEFAULT, Config
from ..errors import DependencyMissingError, MiningTimeoutError, NotAGitRepositoryError
from ..logging_utils import get_logger

log = get_logger("extract.driller")

try:
    from pydriller import Repository as _PDRepository

    _HAVE_PYDRILLER = True
except Exception:  # pragma: no cover
    _HAVE_PYDRILLER = False


@dataclass
class FileStat:
    path: str
    commits: int = 0
    insertions: int = 0
    deletions: int = 0
    bugfixes: int = 0
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    authors: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    @property
    def churn(self) -> int:
        return self.insertions + self.deletions


@dataclass
class History:
    """Structured, LLM-free record of a repository's Git history."""

    repo: str
    files: dict[str, FileStat] = field(default_factory=dict)
    authors: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    commits: list[dict] = field(default_factory=list)
    cochange: dict[tuple[str, str], int] = field(default_factory=lambda: defaultdict(int))
    mined_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def file_commits(self) -> dict[str, int]:
        return {p: f.commits for p, f in self.files.items()}

    def hashes(self) -> set[str]:
        return {c["hash"] for c in self.commits}


def DEFAULT_BUGFIX(msg: str) -> bool:
    """True if a commit message looks like a bug fix."""
    return bool(_BUGFIX.search(msg or ""))


def _excluded(path: str, excludes: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pat) for pat in excludes)


def ensure_git_repo(path: str) -> None:
    """Raise NotAGitRepositoryError if `path` is not inside a Git repo."""
    try:
        from git import InvalidGitRepositoryError, NoSuchPathError, Repo
    except Exception:  # pragma: no cover - GitPython always present with pydriller
        return
    try:
        Repo(path, search_parent_directories=True)
    except (InvalidGitRepositoryError, NoSuchPathError) as exc:
        raise NotAGitRepositoryError(f"{path} is not a Git repository.") from exc


def is_shallow(path: str) -> bool:
    from pathlib import Path

    try:
        from git import Repo

        git_dir = Path(Repo(path, search_parent_directories=True).git_dir)
        return (git_dir / "shallow").exists()
    except Exception:  # pragma: no cover
        return False


def _ingest_commit(commit, hist: History, cfg: Config) -> None:
    """Fold one PyDriller commit into the History."""
    when = commit.author_date
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    author = commit.author.name or commit.author.email or "unknown"
    bug = DEFAULT_BUGFIX(commit.msg)
    hist.authors[author] += 1

    touched: list[str] = []
    c_churn = 0
    mods = commit.modified_files
    if len(mods) > cfg.max_commit_files:  # skip vendored/generated mega-commits
        log.debug("skipping file-level detail for %s (%d files)", commit.hash[:10], len(mods))
        mods = []
    for mod in mods:
        fpath = mod.new_path or mod.old_path
        if not fpath or _excluded(fpath, cfg.excludes):
            continue
        added = mod.added_lines or 0  # None for binary files
        deleted = mod.deleted_lines or 0
        fs = hist.files.get(fpath)
        if fs is None:
            fs = FileStat(path=fpath, first_seen=when)
            hist.files[fpath] = fs
        fs.commits += 1
        fs.insertions += added
        fs.deletions += deleted
        fs.authors[author] += 1
        fs.last_seen = when
        if fs.first_seen is None or when < fs.first_seen:
            fs.first_seen = when
        if bug:
            fs.bugfixes += 1
        c_churn += added + deleted
        touched.append(fpath)

    if 2 <= len(touched) <= 30:  # temporal coupling, cap fan-out
        for a, b in itertools.combinations(sorted(set(touched)), 2):
            hist.cochange[(a, b)] += 1

    hist.commits.append(
        {
            "hash": commit.hash,
            "author": author,
            "timestamp": when.timestamp(),
            "date": when.isoformat(),
            "is_bugfix": bug,
            "churn": c_churn,
            "files": len(touched),
            "message": (commit.msg or "").splitlines()[0][:200] if commit.msg else "",
        }
    )


def drill(
    path: str,
    since: datetime | None = None,
    branch: str | None = None,
    max_commits: int | None = None,
    only_commits: list[str] | None = None,
    timeout: float | None = None,
    cfg: Config = DEFAULT,
) -> History:
    """Mine `path` into a History.

    Raises NotAGitRepositoryError for a bad path, DependencyMissingError if
    PyDriller is absent, MiningTimeoutError if `timeout` seconds elapse.
    """
    if not _HAVE_PYDRILLER:
        raise DependencyMissingError("PyDriller not installed; cannot mine repository.")
    ensure_git_repo(path)
    if is_shallow(path):
        log.warning("%s is a shallow clone; history is incomplete.", path)

    hist = History(repo=path)
    kwargs: dict[str, object] = {}
    if since:
        kwargs["since"] = since
    if branch:
        kwargs["only_in_branch"] = branch
    if only_commits is not None:
        kwargs["only_commits"] = list(only_commits)

    start = time.monotonic()
    count = 0
    for commit in _PDRepository(path, **kwargs).traverse_commits():
        if max_commits and count >= max_commits:
            break
        if cfg.skip_merges and len(commit.parents) > 1:
            continue
        if timeout is not None and (time.monotonic() - start) > timeout:
            raise MiningTimeoutError(f"Mining exceeded {timeout}s after {count} commits.")
        count += 1
        _ingest_commit(commit, hist, cfg)
        if count % cfg.progress_every == 0:
            log.info("mined %d commits (%d files so far)...", count, len(hist.files))
    log.info("mined %d commits, %d files from %s", len(hist.commits), len(hist.files), path)
    return hist


def merge_histories(base: History, *others: History) -> History:
    """Additively merge histories (used by parallel/incremental mining).

    All per-file and per-author counts are sums; commits are concatenated;
    co-change counts are summed. Aggregates are order-independent.
    """
    for other in others:
        base.authors = _merge_counts(base.authors, other.authors)
        for path, ofs in other.files.items():
            bfs = base.files.get(path)
            if bfs is None:
                base.files[path] = ofs
                continue
            bfs.commits += ofs.commits
            bfs.insertions += ofs.insertions
            bfs.deletions += ofs.deletions
            bfs.bugfixes += ofs.bugfixes
            bfs.authors = _merge_counts(bfs.authors, ofs.authors)
            bfs.first_seen = _min_dt(bfs.first_seen, ofs.first_seen)
            bfs.last_seen = _max_dt(bfs.last_seen, ofs.last_seen)
        base.commits.extend(other.commits)
        for key, n in other.cochange.items():
            base.cochange[key] += n
    return base


def _merge_counts(a: dict[str, int], b: dict[str, int]) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for d in (a, b):
        for k, v in d.items():
            out[k] += v
    return out


def _min_dt(a: datetime | None, b: datetime | None) -> datetime | None:
    return min(x for x in (a, b) if x is not None) if (a or b) else None


def _max_dt(a: datetime | None, b: datetime | None) -> datetime | None:
    return max(x for x in (a, b) if x is not None) if (a or b) else None
