"""Multi-tenant project registry: serve many repositories from one process.

Each repository is a *project*, keyed by a stable hash of its path. Reports are
persisted via the ReportStore (survive restarts) and cached in memory. Mining of
a given project is guarded by a per-project lock so concurrent requests for the
same repo mine once; different projects mine independently. Sync FastAPI
endpoints run in Starlette's threadpool, so many users hitting different projects
are served concurrently.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .logging_utils import get_logger
from .report.builder import analyze
from .storage import DEFAULT_STORE, ReportStore, project_key

log = get_logger("registry")


@dataclass
class Project:
    key: str
    repo: str
    since_days: int | None = None
    max_commits: int | None = None


class ProjectRegistry:
    def __init__(self, store: ReportStore | None = None, top: int = 50):
        self._store = store or DEFAULT_STORE
        self._top = top
        self._projects: dict[str, Project] = {}
        self._reports: dict[str, dict] = {}
        self._reg_lock = threading.Lock()
        self._mine_locks: dict[str, threading.Lock] = {}

    # --- registration -------------------------------------------------
    def register(
        self, repo: str, since_days: int | None = None, max_commits: int | None = None
    ) -> str:
        key = project_key(repo)
        with self._reg_lock:
            self._projects[key] = Project(key, repo, since_days, max_commits)
            self._mine_locks.setdefault(key, threading.Lock())
        return key

    def resolve(self, project: str | None = None, repo: str | None = None) -> str:
        """Return a project key from a key, a repo path, or raise."""
        if repo:
            return self.register(repo)
        if project:
            if project in self._projects:
                return project
            # maybe a repo path was passed as `project`
            key = project_key(project)
            if key in self._projects or self._store.get(project) is not None:
                self.register(project)
                return key
            return project  # a bare key we may still find in the store
        raise KeyError("no project specified")

    # --- data ---------------------------------------------------------
    def _lock_for(self, key: str) -> threading.Lock:
        with self._reg_lock:
            return self._mine_locks.setdefault(key, threading.Lock())

    def get_report(self, key: str) -> dict | None:
        if key in self._reports:
            return self._reports[key]
        proj = self._projects.get(key)
        stored = self._store.get(proj.repo) if proj else _store_get_by_key(self._store, key)
        if stored is not None:
            self._reports[key] = stored
            return stored
        if proj is None:
            return None
        return self.mine(key)

    def mine(self, key: str) -> dict:
        proj = self._projects[key]
        with self._lock_for(key):  # one mine per project at a time
            since = None
            if proj.since_days:
                since = datetime.now(timezone.utc) - timedelta(days=proj.since_days)
            rep = analyze(
                proj.repo, since=since, max_commits=proj.max_commits, top=self._top, validate=True
            )
            self._reports[key] = rep
            self._store.put(proj.repo, rep)
            return rep

    # --- management ---------------------------------------------------
    def list(self) -> list[dict]:
        """Registered + persisted projects, de-duplicated by key."""
        out: dict[str, dict] = {}
        for m in self._store.list():
            out[m.project_key] = {
                "project": m.project_key,
                "repo": m.repo,
                "commits": m.n_commits,
                "files": m.n_files,
                "health": m.health,
                "loaded": m.project_key in self._reports,
            }
        for key, p in self._projects.items():
            out.setdefault(
                key,
                {
                    "project": key,
                    "repo": p.repo,
                    "commits": None,
                    "files": None,
                    "health": None,
                    "loaded": key in self._reports,
                },
            )
        return list(out.values())

    def clear(self, key: str) -> dict:
        from .storage import purge

        proj = self._projects.get(key)
        repo = proj.repo if proj else _store_repo_by_key(self._store, key)
        self._reports.pop(key, None)
        if repo is None:
            return {"repo": None, "report_removed": False, "cache_files_removed": 0}
        return purge(repo, store=self._store)


def _store_get_by_key(store: ReportStore, key: str) -> dict | None:
    for m in store.list():
        if m.project_key == key:
            return store.get(m.repo)
    return None


def _store_repo_by_key(store: ReportStore, key: str) -> str | None:
    for m in store.list():
        if m.project_key == key:
            return m.repo
    return None
