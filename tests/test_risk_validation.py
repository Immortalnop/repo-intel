"""Back-test the bug-proneness model against ground-truth labels.

We synthesize a repo where some modules are deliberately 'buggy' (many
fix/revert commits, high churn) and others are 'clean' (feature commits only).
The model must rank buggy modules above clean ones. This turns the hand-tuned
weights from an assertion into a measured claim (precision@k, separation).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from repo_intel.report.builder import analyze

BUGGY = [f"src/buggy_{i}.py" for i in range(1, 4)]
CLEAN = [f"src/clean_{i}.py" for i in range(1, 4)]


def _run(cmd, cwd, env=None):
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, env=env)


def _commit(root, name, email, date, msg):
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


def _write(root, rel, n):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(f"line{i}" for i in range(n)) + "\n")


@pytest.fixture(scope="module")
def labeled_report(tmp_path_factory):
    root = tmp_path_factory.mktemp("labeled")
    _run(["git", "init", "-q"], root)
    _run(["git", "config", "user.email", "d@x.com"], root)
    _run(["git", "config", "user.name", "Dev"], root)

    # buggy modules: 8 commits each, mostly fixes/reverts, large churn
    for month in range(1, 9):
        for f in BUGGY:
            _write(root, f, 40 + month * 20)
        msg = "fix regression" if month % 2 else "revert broken change"
        _commit(root, "Dev", "d@x.com", f"2026-0{month}-05T10:00:00", msg)
    # clean modules: 8 commits each, features only, small churn
    for month in range(1, 9):
        for f in CLEAN:
            _write(root, f, 10 + month)
        _commit(root, "Dev", "d@x.com", f"2026-0{month}-06T10:00:00", f"add feature {month}")

    return analyze(str(root), top=50)


def test_buggy_modules_rank_higher(labeled_report):
    ranked = [h["path"] for h in labeled_report["hotspots"]]
    top3 = set(ranked[:3])
    precision_at_3 = len(top3 & set(BUGGY)) / 3
    assert precision_at_3 >= 0.66, f"precision@3={precision_at_3}, ranking={ranked}"


def test_risk_separation(labeled_report):
    scores = {h["path"]: h["risk_score"] for h in labeled_report["all_files"]}
    mean_buggy = sum(scores[f] for f in BUGGY) / len(BUGGY)
    mean_clean = sum(scores[f] for f in CLEAN) / len(CLEAN)
    assert mean_buggy > mean_clean + 10, f"buggy={mean_buggy:.1f} clean={mean_clean:.1f}"


def test_buggy_have_higher_bugfix_ratio(labeled_report):
    rows = {r["path"]: r for r in labeled_report["all_files"]}
    assert all(rows[f]["bugfix_ratio"] > rows[c]["bugfix_ratio"] for f in BUGGY for c in CLEAN)
