"""API persistence: report survives via the store; /api/clear and /api/store."""

import pytest
from fastapi.testclient import TestClient

from repo_intel.api import routes
from repo_intel.api.server import app
from repo_intel.storage import ReportStore


@pytest.fixture
def client(demo_repo, tmp_path, monkeypatch):
    store = ReportStore(tmp_path / "store.sqlite")
    monkeypatch.setattr(routes, "DEFAULT_STORE", store)
    monkeypatch.setattr("repo_intel.extract.cache.CACHE_DIR", tmp_path / "cache")
    routes.STATE.update(repo=demo_repo, since_days=None, max_commits=None, report=None)
    return TestClient(app), store


def test_mine_persists_to_store(client):
    c, store = client
    c.get("/api/report")  # triggers mine
    assert store.get(routes.STATE["repo"]) is not None
    assert store.list()[0].n_commits > 0


def test_report_loads_from_store_without_mining(client, monkeypatch):
    c, store = client
    c.get("/api/report")  # populate store
    routes.STATE["report"] = None  # simulate restart (in-memory lost)

    # if it re-mines this would call analyze; assert it uses the store instead
    called = {"mine": False}
    real_mine = routes.mine
    monkeypatch.setattr(routes, "mine", lambda: called.__setitem__("mine", True) or real_mine())

    r = c.get("/api/report")
    assert r.status_code == 200
    assert called["mine"] is False  # served from persistent store


def test_store_endpoint_lists_projects(client):
    c, _ = client
    c.get("/api/report")
    body = c.get("/api/store").json()
    assert body["projects"] and body["projects"][0]["n_commits"] > 0


def test_clear_endpoint(client):
    c, store = client
    c.get("/api/report")
    assert store.get(routes.STATE["repo"]) is not None
    r = c.post("/api/clear")
    assert r.status_code == 200
    assert r.json()["status"] == "cleared"
    assert store.get(routes.STATE["repo"]) is None
    assert routes.STATE["report"] is None


def test_multi_project_endpoints(client, tmp_path, monkeypatch):
    import subprocess

    from repo_intel.registry import ProjectRegistry
    from repo_intel.storage import ReportStore

    c, store = client
    monkeypatch.setattr(routes, "REGISTRY", ProjectRegistry(ReportStore(tmp_path / "reg.sqlite")))

    other = tmp_path / "proj2"
    other.mkdir()
    env = {
        "GIT_AUTHOR_NAME": "Z",
        "GIT_AUTHOR_EMAIL": "z@x.com",
        "GIT_COMMITTER_NAME": "Z",
        "GIT_COMMITTER_EMAIL": "z@x.com",
    }
    subprocess.run(["git", "init", "-q"], cwd=other, check=True)
    (other / "y.py").write_text("def a():\n    return 1\n")
    subprocess.run(["git", "add", "-A"], cwd=other, check=True, env=env)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=other, check=True, env=env)

    reg = c.post(f"/api/projects?repo={other}")
    assert reg.status_code == 200
    key = reg.json()["project"]

    # default repo and the new project are both served, independently
    assert c.get("/api/report").json()["summary"]["commits"] == 21
    assert c.get(f"/api/report?project={key}").json()["summary"]["commits"] == 1
    assert any(p["project"] == key for p in c.get("/api/projects").json()["projects"])
