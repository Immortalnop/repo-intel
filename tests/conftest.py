"""Shared fixtures: a deterministic on-disk git repo built via subprocess.

The repo is crafted so every metric has something to find:
  core/engine.py   Alice-owned, high churn, many bug-fixes  -> hotspot
  utils/helpers.py Bob-only                                 -> knowledge silo
  api/routes.py    co-changed with core/engine.py (Carol)   -> cross-module drift
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def _run(cmd, cwd, env=None):
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, env=env)


def _write(root: Path, rel: str, n: int):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(f"line{i}" for i in range(n)) + "\n")


def _commit(root: Path, name: str, email: str, date: str, msg: str):
    import os

    env = {
        **os.environ,
        "GIT_AUTHOR_DATE": date,
        "GIT_COMMITTER_DATE": date,
        "GIT_AUTHOR_NAME": name,
        "GIT_AUTHOR_EMAIL": email,
        "GIT_COMMITTER_NAME": name,
        "GIT_COMMITTER_EMAIL": email,
    }
    _run(["git", "add", "-A"], root, env)
    _run(["git", "commit", "-q", "-m", msg], root, env)


@pytest.fixture(scope="session")
def demo_repo(tmp_path_factory) -> str:
    root = tmp_path_factory.mktemp("demo_repo")
    _run(["git", "init", "-q"], root)
    _run(["git", "config", "user.email", "a@x.com"], root)
    _run(["git", "config", "user.name", "Alice"], root)

    # Alice: engine.py hotspot (churn + bug-fixes), some routes.py
    for i in range(1, 13):
        _write(root, "core/engine.py", 20 + i * 5)
        _write(root, "api/routes.py", 10 + i)
        msg = f"fix crash in engine path {i}" if i % 2 == 0 else f"feature work {i}"
        _commit(root, "Alice", "a@x.com", f"2026-0{(i % 9) + 1}-10T10:00:00", msg)
    # Bob: helpers.py only -> silo
    for i in range(1, 5):
        _write(root, "utils/helpers.py", 5 + i)
        _commit(root, "Bob", "b@x.com", f"2026-0{(i % 9) + 1}-15T09:00:00", f"add helper {i}")
    # Carol: routes.py + engine.py together -> cross-module coupling
    for i in range(1, 6):
        _write(root, "api/routes.py", 30 + i)
        _write(root, "core/engine.py", 90 + i)
        _commit(
            root, "Carol", "c@x.com", f"2026-09-0{i}T08:00:00", f"bugfix: sync routes+engine {i}"
        )
    return str(root)


@pytest.fixture(scope="session")
def report(demo_repo):
    from repo_intel.report.builder import analyze

    return analyze(demo_repo, validate=True, top=50)
