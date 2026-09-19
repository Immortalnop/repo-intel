"""Persistent report store: sqlite + gzip, keyed per repository/project.

Replaces the API's in-memory-only state so a mined report survives restarts,
and lets you clear stored data one project at a time (or all of it). Reports are
gzip-compressed JSON blobs in a single sqlite file, so the store is compact and
needs no external service.

Layout: <data>/store.sqlite  (data dir from REPO_INTEL_DATA, default ./data)
"""

from __future__ import annotations

import gzip
import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from .config import DATA_DIR
from .logging_utils import get_logger

log = get_logger("storage")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    project_key TEXT PRIMARY KEY,
    repo        TEXT NOT NULL,
    generated_at TEXT,
    head        TEXT,
    n_commits   INTEGER,
    n_files     INTEGER,
    health      REAL,
    report_gz   BLOB NOT NULL,
    updated_at  REAL NOT NULL
);
"""


@dataclass
class StoredMeta:
    project_key: str
    repo: str
    generated_at: str | None
    head: str | None
    n_commits: int
    n_files: int
    health: float | None
    updated_at: float


def project_key(repo: str) -> str:
    """Stable key for a repo/project: sha1 of its absolute path."""
    return hashlib.sha1(str(Path(repo).resolve()).encode()).hexdigest()[:16]


class ReportStore:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path else (DATA_DIR / "store.sqlite")

    def _conn(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.executescript(_SCHEMA)
        return con

    # --- write --------------------------------------------------------
    def put(self, repo: str, report: dict) -> None:
        blob = gzip.compress(json.dumps(report, default=str).encode())
        s = report.get("summary", {})
        con = self._conn()
        with con:
            con.execute(
                "INSERT INTO reports("
                "project_key,repo,generated_at,head,n_commits,n_files,health,report_gz,updated_at"
                ") VALUES(?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(project_key) DO UPDATE SET "
                "repo=excluded.repo, generated_at=excluded.generated_at, head=excluded.head, "
                "n_commits=excluded.n_commits, n_files=excluded.n_files, health=excluded.health, "
                "report_gz=excluded.report_gz, updated_at=excluded.updated_at",
                (
                    project_key(repo),
                    repo,
                    report.get("generated_at"),
                    report.get("git", {}).get("head"),
                    s.get("commits", 0),
                    s.get("files", 0),
                    s.get("health_score"),
                    blob,
                    time.time(),
                ),
            )
        con.close()
        log.info("stored report for %s (%d bytes gz)", repo, len(blob))

    # --- read ---------------------------------------------------------
    def get(self, repo: str) -> dict | None:
        con = self._conn()
        row = con.execute(
            "SELECT report_gz FROM reports WHERE project_key=?", (project_key(repo),)
        ).fetchone()
        con.close()
        if row is None:
            return None
        return json.loads(gzip.decompress(row["report_gz"]).decode())

    def list(self) -> list[StoredMeta]:
        con = self._conn()
        rows = con.execute(
            "SELECT project_key,repo,generated_at,head,n_commits,n_files,health,updated_at "
            "FROM reports ORDER BY updated_at DESC"
        ).fetchall()
        con.close()
        return [
            StoredMeta(
                project_key=r["project_key"],
                repo=r["repo"],
                generated_at=r["generated_at"],
                head=r["head"],
                n_commits=r["n_commits"],
                n_files=r["n_files"],
                health=r["health"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ]

    # --- delete -------------------------------------------------------
    def delete(self, repo: str) -> bool:
        con = self._conn()
        with con:
            cur = con.execute("DELETE FROM reports WHERE project_key=?", (project_key(repo),))
        con.close()
        return cur.rowcount > 0

    def clear_all(self) -> int:
        con = self._conn()
        with con:
            cur = con.execute("DELETE FROM reports")
        con.close()
        return cur.rowcount


# module-level default store
DEFAULT_STORE = ReportStore()


def purge(repo: str, store: ReportStore | None = None) -> dict:
    """Clear all persisted data for one repo: stored report + mining cache."""
    store = store or DEFAULT_STORE
    removed_report = store.delete(repo)
    from .extract import cache

    removed_cache = cache.clear(repo)
    log.info("purged %s (report=%s, cache_files=%d)", repo, removed_report, removed_cache)
    return {"repo": repo, "report_removed": removed_report, "cache_files_removed": removed_cache}
