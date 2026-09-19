"""Tier 4 metrics: complexity, issue linkage, departure risk."""

import pytest

from repo_intel.metrics import commit_intel, complexity, knowledge


def test_complexity_multi_language(tmp_path):
    if not complexity.available():
        pytest.skip("lizard not installed")
    (tmp_path / "m.py").write_text(
        "def f(x):\n    if x > 0:\n        return 1\n"
        "    elif x < 0:\n        return -1\n    return 0\n"
    )
    (tmp_path / "s.js").write_text("function g(x){ if(x>0){return 1} return 0 }\n")
    (tmp_path / "t.go").write_text(
        "package m\nfunc h(x int) int { if x>0 { return 1 }; return 0 }\n"
    )
    cx = complexity.file_complexity(str(tmp_path), ["m.py", "s.js", "t.go"])
    assert set(cx) == {"m.py", "s.js", "t.go"}
    assert cx["m.py"]["language"] == "python"
    assert cx["s.js"]["language"] == "javascript"
    assert cx["t.go"]["language"] == "go"
    assert cx["m.py"]["max"] >= 3


def test_complexity_skips_unknown_extension(tmp_path):
    (tmp_path / "a.txt").write_text("hello")
    assert complexity.file_complexity(str(tmp_path), ["a.txt"]) == {}


def test_issue_linkage_counts():
    commits = [
        {"is_bugfix": True, "message": "fix crash (#123)", "files": 1, "churn": 3},
        {"is_bugfix": True, "message": "fix typo", "files": 1, "churn": 1},
        {"is_bugfix": False, "message": "feature ABC-42", "files": 1, "churn": 5},
    ]
    s = commit_intel.commit_summary(commits)
    assert s["issue_linked_commits"] == 2  # #123 and ABC-42
    assert s["tracked_bugfixes"] == 1  # only the #123 bugfix


def test_departure_risk(report):
    dr = report["departure_risk"]
    assert dr, "expected at least one silo owner"
    top = dr[0]
    assert top["owned_files"] >= 1
    assert 0 <= top["codebase_share"] <= 1


def test_departure_risk_empty_when_no_silos():
    rows = [
        {"path": "a.py", "top_author": "x", "top_author_share": 0.4, "commits": 10},
        {"path": "b.py", "top_author": "y", "top_author_share": 0.5, "commits": 10},
    ]
    assert knowledge.departure_risk(rows) == []
