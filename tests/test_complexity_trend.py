"""Complexity-over-history: sampling and trend series."""

import os
import subprocess

import pytest

from repo_intel.metrics import complexity


def test_sample_commits_bounds():
    commits = [{"timestamp": i, "hash": f"h{i}"} for i in range(100)]
    s = complexity.sample_commits(commits, points=8)
    assert len(s) == 8
    assert s[0]["timestamp"] == 0
    assert s[-1]["timestamp"] == 99  # spans full range


def test_sample_commits_small_input():
    commits = [{"timestamp": 1, "hash": "a"}, {"timestamp": 2, "hash": "b"}]
    assert complexity.sample_commits(commits, points=8) == commits


@pytest.fixture
def evolving_repo(tmp_path):
    repo = tmp_path / "evo"
    repo.mkdir()
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Z",
        "GIT_AUTHOR_EMAIL": "z@x.com",
        "GIT_COMMITTER_NAME": "Z",
        "GIT_COMMITTER_EMAIL": "z@x.com",
    }
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    for n in range(1, 6):
        # each commit adds a function with growing branching
        body = (
            "def f(x):\n"
            + "".join(f"    if x=={i}:\n        return {i}\n" for i in range(n))
            + "    return -1\n"
        )
        (repo / "m.py").write_text(body)
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, env=env)
        subprocess.run(
            ["git", "commit", "-qm", f"grow {n}", f"--date=2026-0{n}-01T10:00:00"],
            cwd=repo,
            check=True,
            env={**env, "GIT_COMMITTER_DATE": f"2026-0{n}-01T10:00:00"},
        )
    return str(repo)


def test_complexity_trend_over_history(evolving_repo):
    if not complexity.available():
        pytest.skip("lizard not installed")
    from repo_intel.extract import driller

    hist = driller.drill(evolving_repo)
    trend = complexity.complexity_trend(evolving_repo, hist.commits, points=5)
    assert len(trend) >= 3
    # complexity should not decrease as branches are added
    assert trend[-1]["avg_complexity"] >= trend[0]["avg_complexity"]


def test_report_includes_trend_when_requested(evolving_repo):
    if not complexity.available():
        pytest.skip("lizard not installed")
    from repo_intel.report.builder import analyze

    rep = analyze(evolving_repo, complexity_trend=True)
    assert rep["complexity_trend"]
    rep2 = analyze(evolving_repo, complexity_trend=False)
    assert rep2["complexity_trend"] == []
