"""Mining orchestration: serial, parallel (--jobs) and incremental drilling.

Parallel mining assigns each commit hash to exactly one worker (PyDriller's
`only_commits`) and additively merges the partial histories, so the result is
identical to a serial mine but faster on large repositories.
Incremental mining drills only commits absent from a cached history.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime

from ..config import DEFAULT, Config
from ..logging_utils import get_logger
from .driller import History, drill, ensure_git_repo, merge_histories

log = get_logger("extract.mine")


def list_commit_hashes(path: str, branch: str | None = None) -> list[str]:
    """Ordered short hashes reachable from HEAD (or `branch`)."""
    from git import Repo

    repo = Repo(path, search_parent_directories=True)
    rev = branch or repo.head.reference
    return [c.hexsha for c in repo.iter_commits(rev)]


def _chunk(seq: list[str], n: int) -> list[list[str]]:
    n = max(1, n)
    size = (len(seq) + n - 1) // n
    return [seq[i : i + size] for i in range(0, len(seq), size)] or [[]]


def _drill_chunk(args: tuple[str, list[str], Config]) -> History:
    """Drill a hash subset in an isolated local clone.

    PyDriller mutates .git/config on open, so multiple workers cannot share one
    working copy. A `--local` clone is a cheap (hard-linked) private copy that
    sidesteps the config lock entirely.
    """
    path, hashes, cfg = args
    tmp = tempfile.mkdtemp(prefix="repo_intel_worker_")
    try:
        subprocess.run(
            ["git", "clone", "--local", "--no-hardlinks", "--quiet", path, tmp],
            check=True,
            capture_output=True,
        )
        hist = drill(tmp, only_commits=hashes, cfg=cfg)
        hist.repo = path  # report the original path, not the temp clone
        return hist
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def drill_parallel(
    path: str,
    jobs: int,
    branch: str | None = None,
    cfg: Config = DEFAULT,
) -> History:
    """Mine with `jobs` worker processes. Falls back to serial for jobs<=1."""
    ensure_git_repo(path)
    if jobs <= 1:
        return drill(path, branch=branch, cfg=cfg)
    hashes = list_commit_hashes(path, branch)
    if len(hashes) < jobs * 2:  # not worth the process overhead
        return drill(path, branch=branch, cfg=cfg)
    chunks = _chunk(hashes, jobs)
    log.info("parallel mine: %d commits across %d workers", len(hashes), len(chunks))
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        parts = list(ex.map(_drill_chunk, [(path, c, cfg) for c in chunks]))
    base = History(repo=path)
    return merge_histories(base, *parts)


def drill_incremental(
    path: str,
    cached: History,
    branch: str | None = None,
    cfg: Config = DEFAULT,
) -> History:
    """Extend a cached history with only the commits it doesn't already have."""
    ensure_git_repo(path)
    current = list_commit_hashes(path, branch)
    known = cached.hashes()
    new = [h for h in current if h not in known]
    if not new:
        log.info("incremental mine: already up to date (%d commits)", len(known))
        return cached
    log.info("incremental mine: %d new commits", len(new))
    fresh = drill(path, only_commits=new, cfg=cfg)
    merged = merge_histories(cached, fresh)
    merged.mined_at = datetime.now(fresh.mined_at.tzinfo)
    return merged
