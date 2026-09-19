"""Tier 2: edge cases, parallel-mining equivalence, incremental mining, timeout."""

import os
import subprocess

import pytest

from repo_intel.errors import (
    EmptyRepositoryError,
    MiningTimeoutError,
    NotAGitRepositoryError,
)
from repo_intel.extract import driller, mine
from repo_intel.report.builder import analyze


def test_non_git_path_raises(tmp_path):
    with pytest.raises(NotAGitRepositoryError):
        analyze(str(tmp_path))


def test_empty_repo_raises(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    with pytest.raises(EmptyRepositoryError):
        analyze(str(tmp_path))


def test_parallel_equals_serial(demo_repo):
    serial = analyze(demo_repo, jobs=1)
    parallel = analyze(demo_repo, jobs=3)
    assert serial["summary"]["total_churn"] == parallel["summary"]["total_churn"]
    assert serial["summary"]["commits"] == parallel["summary"]["commits"]
    assert [h["path"] for h in serial["hotspots"]] == [h["path"] for h in parallel["hotspots"]]
    assert serial["coupling"] == parallel["coupling"]


def test_incremental_no_new_commits(demo_repo):
    base = driller.drill(demo_repo)
    merged = mine.drill_incremental(demo_repo, base)
    assert len(merged.commits) == len(base.commits)


def test_incremental_picks_up_new_commit(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "T",
        "GIT_AUTHOR_EMAIL": "t@x.com",
        "GIT_COMMITTER_NAME": "T",
        "GIT_COMMITTER_EMAIL": "t@x.com",
    }
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / "a.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, env=env)
    subprocess.run(["git", "commit", "-qm", "first"], cwd=repo, check=True, env=env)

    base = driller.drill(str(repo))
    assert len(base.commits) == 1

    (repo / "b.py").write_text("y = 2\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, env=env)
    subprocess.run(["git", "commit", "-qm", "second"], cwd=repo, check=True, env=env)

    merged = mine.drill_incremental(str(repo), base)
    assert len(merged.commits) == 2
    assert "b.py" in merged.files


def test_timeout_raises(demo_repo, monkeypatch):
    # force elapsed time to exceed the budget immediately
    seq = iter([0.0] + [100.0] * 100)
    monkeypatch.setattr(driller.time, "monotonic", lambda: next(seq))
    with pytest.raises(MiningTimeoutError):
        driller.drill(demo_repo, timeout=1.0)


def test_binary_none_lines_safe(tmp_path):
    # PyDriller reports None added/deleted for binary files; must not crash.
    repo = tmp_path / "b"
    repo.mkdir()
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "T",
        "GIT_AUTHOR_EMAIL": "t@x.com",
        "GIT_COMMITTER_NAME": "T",
        "GIT_COMMITTER_EMAIL": "t@x.com",
    }
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / "logo.bin").write_bytes(bytes(range(256)) * 4)
    (repo / "code.py").write_text("print(1)\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, env=env)
    subprocess.run(["git", "commit", "-qm", "add binary + code"], cwd=repo, check=True, env=env)

    hist = driller.drill(str(repo))
    assert "code.py" in hist.files  # did not crash on the binary
