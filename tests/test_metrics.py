"""Unit tests for the deterministic metric functions (no Git, no LLM)."""

from datetime import datetime, timedelta, timezone

from repo_intel.analysis import predict
from repo_intel.metrics import bugproneness, churn, drift, ownership, release

NOW = datetime(2026, 9, 18, tzinfo=timezone.utc)


def test_bus_factor_single_owner():
    assert ownership.bus_factor({"a": 10}) == 1
    assert ownership.bus_factor({"a": 5, "b": 5}) == 1  # a alone reaches 50%
    assert ownership.bus_factor({"a": 3, "b": 3, "c": 3, "d": 3}) == 2


def test_ownership_share():
    top, share = ownership.ownership_share({"a": 8, "b": 2})
    assert top == "a" and abs(share - 0.8) < 1e-9


def test_recency_halflife():
    r_now = churn.recency_weight(NOW, NOW, 90)
    r_old = churn.recency_weight(NOW - timedelta(days=90), NOW, 90)
    assert abs(r_now - 1.0) < 1e-9
    assert abs(r_old - 0.5) < 1e-6


def test_risk_score_bounds_and_monotonic():
    lo, _ = bugproneness.file_risk_score(1, 1, 0, NOW - timedelta(days=400), {"a": 1}, 100, NOW)
    hi, _ = bugproneness.file_risk_score(100, 10, 8, NOW, {"a": 10}, 100, NOW)
    assert 0 <= lo <= 100 and 0 <= hi <= 100
    assert hi > lo


def test_coupling_cross_module():
    cc = {("api/x.py", "core/y.py"): 5}
    fc = {"api/x.py": 5, "core/y.py": 6}
    out = drift.temporal_coupling(cc, fc)
    assert out and out[0]["cross_module"] is True


def test_release_verdict():
    commits = [{"timestamp": NOW.timestamp(), "is_bugfix": False, "churn": 5}] * 10
    rr = release.release_readiness(commits, [], NOW)
    assert rr["verdict"] in ("READY", "CAUTION", "NOT READY")


def test_predict_trend():
    act = [{"month": f"2026-0{i}", "commits": 10, "bugfixes": i, "churn": 100} for i in range(1, 6)]
    p = predict.predict_risk(act)
    assert p["trend"] == "DETERIORATING"
