"""Tier 3: health endpoints, bearer auth, rate limiting."""

import importlib

import pytest
from fastapi.testclient import TestClient


def _fresh_app(demo_repo, monkeypatch, **env):
    """Rebuild the app so security middleware picks up env vars."""
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    from repo_intel.api import routes, security, server

    importlib.reload(security)
    importlib.reload(server)
    server.routes.STATE.update(repo=demo_repo, since_days=None, max_commits=None, report=None)
    return server.app, routes


def test_healthz_open(demo_repo, monkeypatch):
    app, _ = _fresh_app(demo_repo, monkeypatch)
    c = TestClient(app)
    assert c.get("/healthz").json()["status"] == "ok"


def test_readyz_pending_then_ready(demo_repo, monkeypatch):
    app, routes = _fresh_app(demo_repo, monkeypatch)
    c = TestClient(app)
    assert c.get("/readyz").status_code == 503  # nothing mined yet
    c.get("/api/report")  # triggers a mine
    assert c.get("/readyz").status_code == 200


def test_auth_required_when_token_set(demo_repo, monkeypatch):
    app, _ = _fresh_app(demo_repo, monkeypatch, REPO_INTEL_API_TOKEN="secret")
    c = TestClient(app)
    assert c.get("/api/flags").status_code == 401
    assert c.get("/api/flags", headers={"Authorization": "Bearer secret"}).status_code == 200
    assert c.get("/healthz").status_code == 200  # health stays open


def test_rate_limit(demo_repo, monkeypatch):
    app, _ = _fresh_app(demo_repo, monkeypatch, REPO_INTEL_RATE_LIMIT="3")
    c = TestClient(app)
    codes = [c.get("/api/flags").status_code for _ in range(5)]
    assert 429 in codes
    assert codes[:3] == [200, 200, 200]


@pytest.fixture(autouse=True)
def _restore_modules():
    """Reload server/security clean after these tests mutate env-derived state."""
    yield
    from repo_intel.api import security, server

    importlib.reload(security)
    importlib.reload(server)
