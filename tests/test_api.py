"""API layer via FastAPI TestClient."""

import pytest
from fastapi.testclient import TestClient

from repo_intel.api import routes
from repo_intel.api.server import app
from repo_intel.models import Report


@pytest.fixture(scope="module")
def client(demo_repo):
    routes.STATE.update(repo=demo_repo, since_days=None, max_commits=None, report=None)
    return TestClient(app)


def test_report_endpoint_validates(client):
    r = client.get("/api/report")
    assert r.status_code == 200
    Report.model_validate(r.json())


def test_hotspots_endpoint(client):
    r = client.get("/api/hotspots?n=2")
    assert r.status_code == 200
    assert len(r.json()["hotspots"]) == 2


def test_flags_endpoint(client):
    r = client.get("/api/flags")
    assert r.status_code == 200
    assert any(f["code"] == "BUG_PRONE_MODULE" for f in r.json()["flags"])


def test_predict_endpoint(client):
    r = client.get("/api/predict")
    assert r.status_code == 200
    assert "trend" in r.json()


def test_summary_fallback(client):
    r = client.get("/api/summary?llm=false")
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "fallback"
    assert body["text"]


def test_refresh(client):
    r = client.post("/api/refresh")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_dashboard_and_plotly(client):
    assert client.get("/").status_code == 200
    js = client.get("/plotly.min.js")
    assert js.status_code == 200
    assert len(js.content) > 100000
