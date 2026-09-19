"""Cache parsed history so repeated CLI commands don't re-mine.

Primary store is SQLite (always available). If pandas + pyarrow are present,
the commit table is also exported to Parquet for external analysis. Keyed by
repo path + mining parameters.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from ..config import CACHE_DIR
from .driller import FileStat, History


def _key(repo: str, since, branch, max_commits) -> str:
    raw = f"{Path(repo).resolve()}|{since}|{branch}|{max_commits}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def _db_path(key: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{key}.sqlite"


def clear(repo: str) -> int:
    """Remove all cached mining artifacts (sqlite + parquet) for one repo.

    Cache keys hash the mining parameters, so files are matched by the `repo`
    recorded inside each cache DB rather than by filename. Returns files removed.
    """
    if not CACHE_DIR.exists():
        return 0
    resolved = str(Path(repo).resolve())
    removed = 0
    for db in CACHE_DIR.glob("*.sqlite"):
        try:
            con = sqlite3.connect(db)
            row = con.execute("SELECT v FROM meta WHERE k='repo'").fetchone()
            con.close()
        except Exception:
            continue
        stored = row[0] if row else None
        if stored and str(Path(stored).resolve()) == resolved:
            key = db.stem
            db.unlink(missing_ok=True)
            removed += 1
            parquet = CACHE_DIR / f"{key}_commits.parquet"
            if parquet.exists():
                parquet.unlink(missing_ok=True)
                removed += 1
    return removed


def clear_all() -> int:
    if not CACHE_DIR.exists():
        return 0
    removed = 0
    for f in CACHE_DIR.glob("*"):
        f.unlink(missing_ok=True)
        removed += 1
    return removed


def save(hist: History, since=None, branch=None, max_commits=None) -> Path:
    key = _key(hist.repo, since, branch, max_commits)
    db = _db_path(key)
    con = sqlite3.connect(db)
    con.executescript(
        "DROP TABLE IF EXISTS meta; DROP TABLE IF EXISTS files;"
        "DROP TABLE IF EXISTS commits; DROP TABLE IF EXISTS cochange;"
        "CREATE TABLE meta(k TEXT, v TEXT);"
        "CREATE TABLE files(path TEXT, commits INT, insertions INT, deletions INT,"
        " bugfixes INT, first_seen TEXT, last_seen TEXT, authors TEXT);"
        "CREATE TABLE commits(hash TEXT, author TEXT, ts REAL, date TEXT,"
        " is_bugfix INT, churn INT, files INT, message TEXT);"
        "CREATE TABLE cochange(a TEXT, b TEXT, n INT);"
    )
    con.execute("INSERT INTO meta VALUES('repo',?)", (hist.repo,))
    con.execute("INSERT INTO meta VALUES('mined_at',?)", (hist.mined_at.isoformat(),))
    con.executemany(
        "INSERT INTO files VALUES(?,?,?,?,?,?,?,?)",
        [
            (
                f.path,
                f.commits,
                f.insertions,
                f.deletions,
                f.bugfixes,
                f.first_seen.isoformat() if f.first_seen else None,
                f.last_seen.isoformat() if f.last_seen else None,
                json.dumps(dict(f.authors)),
            )
            for f in hist.files.values()
        ],
    )
    con.executemany(
        "INSERT INTO commits VALUES(?,?,?,?,?,?,?,?)",
        [
            (
                c["hash"],
                c["author"],
                c["timestamp"],
                c["date"],
                int(c["is_bugfix"]),
                c["churn"],
                c["files"],
                c["message"],
            )
            for c in hist.commits
        ],
    )
    con.executemany(
        "INSERT INTO cochange VALUES(?,?,?)",
        [(a, b, n) for (a, b), n in hist.cochange.items()],
    )
    con.commit()
    con.close()
    _maybe_parquet(hist, key)
    return db


def load(repo: str, since=None, branch=None, max_commits=None) -> History | None:
    key = _key(repo, since, branch, max_commits)
    db = _db_path(key)
    if not db.exists():
        return None
    from datetime import datetime

    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    hist = History(repo=repo)
    meta = {r["k"]: r["v"] for r in con.execute("SELECT * FROM meta")}
    if meta.get("mined_at"):
        hist.mined_at = datetime.fromisoformat(meta["mined_at"])
    for r in con.execute("SELECT * FROM files"):
        fs = FileStat(
            path=r["path"],
            commits=r["commits"],
            insertions=r["insertions"],
            deletions=r["deletions"],
            bugfixes=r["bugfixes"],
            first_seen=datetime.fromisoformat(r["first_seen"]) if r["first_seen"] else None,
            last_seen=datetime.fromisoformat(r["last_seen"]) if r["last_seen"] else None,
        )
        for a, n in json.loads(r["authors"]).items():
            fs.authors[a] = n
        hist.files[fs.path] = fs
    for r in con.execute("SELECT * FROM commits"):
        hist.commits.append(
            {
                "hash": r["hash"],
                "author": r["author"],
                "timestamp": r["ts"],
                "date": r["date"],
                "is_bugfix": bool(r["is_bugfix"]),
                "churn": r["churn"],
                "files": r["files"],
                "message": r["message"],
            }
        )
        hist.authors[r["author"]] += 1
    for r in con.execute("SELECT * FROM cochange"):
        hist.cochange[(r["a"], r["b"])] = r["n"]
    con.close()
    # authors table was rebuilt from commits; recompute cleanly
    from collections import defaultdict

    ac: dict[str, int] = defaultdict(int)
    for c in hist.commits:
        ac[c["author"]] += 1
    hist.authors = ac
    return hist


def _maybe_parquet(hist: History, key: str) -> None:
    try:
        import pandas as pd  # noqa

        df = pd.DataFrame(hist.commits)
        (CACHE_DIR).mkdir(parents=True, exist_ok=True)
        df.to_parquet(CACHE_DIR / f"{key}_commits.parquet", index=False)
    except Exception:
        pass  # parquet is a bonus, never required
