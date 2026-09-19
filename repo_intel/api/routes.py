"""API routes. Holds the mined-report state; server.py wires it into the app."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response

from .. import llm as llm_pkg
from ..models import Narrative, Report
from ..registry import ProjectRegistry
from ..report.builder import analyze
from ..storage import DEFAULT_STORE, purge

router = APIRouter()
# Default single-repo view (backward compatible). Multi-repo goes through REGISTRY.
STATE: dict[str, Any] = {
    "repo": ".",
    "report": None,
    "since_days": None,
    "max_commits": None,
    "cx_trend": False,
}
REGISTRY = ProjectRegistry()
_STATIC = os.path.join(os.path.dirname(__file__), "static")


def mine():
    since = None
    if STATE["since_days"]:
        since = datetime.now(timezone.utc) - timedelta(days=STATE["since_days"])
    rep = analyze(
        STATE["repo"],
        since=since,
        max_commits=STATE["max_commits"],
        top=50,
        validate=True,
        complexity_trend=STATE.get("cx_trend", False),
    )
    STATE["report"] = rep
    DEFAULT_STORE.put(STATE["repo"], rep)  # persist across restarts
    return rep


def report():
    """Default project: in-memory → persistent store → mine."""
    if STATE["report"] is not None:
        return STATE["report"]
    stored = DEFAULT_STORE.get(STATE["repo"])
    if stored is not None:
        STATE["report"] = stored
        return stored
    return mine()


def resolved_report(project: str | None):
    """Serve the default repo when `project` is None, else that project."""
    if not project:
        return report()
    key = REGISTRY.resolve(project=project)
    rep = REGISTRY.get_report(key)
    if rep is None:
        raise HTTPException(status_code=404, detail=f"unknown project: {project}")
    return rep


@router.get("/healthz")
def healthz():
    """Liveness: the process is up."""
    return {"status": "ok"}


@router.get("/readyz")
def readyz():
    """Readiness: a report has been mined and is servable."""
    ready = STATE["report"] is not None
    return JSONResponse(
        {"status": "ready" if ready else "pending", "repo": STATE["repo"]},
        status_code=200 if ready else 503,
    )


@router.get("/api/report", response_model=Report)
def api_report(project: str | None = Query(None)):
    return JSONResponse(resolved_report(project))


@router.get("/api/hotspots")
def api_hotspots(n: int = 20, project: str | None = Query(None)):
    return {"hotspots": resolved_report(project)["hotspots"][:n]}


@router.get("/api/busfactor")
def api_busfactor(n: int = 20, project: str | None = Query(None)):
    return {"knowledge_silos": resolved_report(project)["knowledge_silos"][:n]}


@router.get("/api/drift")
def api_drift(n: int = 20, project: str | None = Query(None)):
    return {"coupling": resolved_report(project)["coupling"][:n]}


@router.get("/api/readiness")
def api_readiness(project: str | None = Query(None)):
    return resolved_report(project)["release_readiness"]


@router.get("/api/predict")
def api_predict(project: str | None = Query(None)):
    return resolved_report(project)["prediction"]


@router.get("/api/flags")
def api_flags(project: str | None = Query(None)):
    return {"flags": resolved_report(project)["flags"]}


@router.get("/api/authors")
def api_authors(project: str | None = Query(None)):
    return {"authors": resolved_report(project)["authors"]}


@router.get("/api/activity")
def api_activity(project: str | None = Query(None)):
    return {"activity": resolved_report(project)["commit_activity"]}


@router.get("/api/summary", response_model=Narrative)
def api_summary(use_llm: bool = Query(False, alias="llm"), project: str | None = Query(None)):
    provider = llm_pkg.get_provider("auto" if use_llm else "none")
    return provider.summarize(resolved_report(project))


@router.post("/api/projects")
def api_register_project(
    repo: str = Query(...),
    since_days: int | None = Query(None),
    max_commits: int | None = Query(None),
):
    """Register and mine an additional repository, served concurrently."""
    key = REGISTRY.register(repo, since_days=since_days, max_commits=max_commits)
    rep = REGISTRY.get_report(key)
    return {"project": key, "repo": repo, "summary": rep["summary"] if rep else None}


@router.get("/api/projects")
def api_list_projects():
    """All projects known to this server (registered + persisted)."""
    return {"projects": REGISTRY.list()}


@router.post("/api/refresh")
def api_refresh(since_days: int | None = Query(None), project: str | None = Query(None)):
    if project:
        key = REGISTRY.resolve(project=project)
        rep = REGISTRY.mine(key)
        return {"status": "ok", "project": key, "generated_at": rep["generated_at"]}
    STATE["since_days"] = since_days
    mine()
    return {"status": "ok", "generated_at": STATE["report"]["generated_at"]}


@router.post("/api/clear")
def api_clear(project: str | None = Query(None)):
    """Clear persisted data for a repo (stored report + mining cache)."""
    if project:
        key = REGISTRY.resolve(project=project)
        return {"status": "cleared", **REGISTRY.clear(key)}
    result = purge(STATE["repo"], store=DEFAULT_STORE)
    STATE["report"] = None  # next request re-mines
    return {"status": "cleared", **result}


@router.get("/api/store")
def api_store():
    """List all persisted projects (for management)."""
    return {"projects": [vars(m) for m in DEFAULT_STORE.list()]}


@router.get("/api/departure")
def api_departure(n: int = 20, project: str | None = Query(None)):
    return {"departure_risk": resolved_report(project)["departure_risk"][:n]}


@router.get("/api/complexity-trend")
def api_complexity_trend(project: str | None = Query(None)):
    """Complexity-over-history for the served repo (computed on demand)."""
    from ..metrics import complexity

    rep = resolved_report(project)
    if rep.get("complexity_trend"):
        return {"complexity_trend": rep["complexity_trend"]}
    # not precomputed: derive from the stored activity months' commits is not enough,
    # so recompute directly from the repo tree at sampled commits.
    from ..extract import driller

    hist = driller.drill(rep["repo"])
    return {"complexity_trend": complexity.complexity_trend(rep["repo"], hist.commits)}


@router.get("/plotly.min.js")
def plotly_js():
    path = os.path.join(_STATIC, "plotly.min.js")
    if os.path.exists(path):
        return FileResponse(path, media_type="application/javascript")
    return Response(status_code=404)


@router.get("/", response_class=HTMLResponse)
def dashboard():
    with open(os.path.join(_STATIC, "dashboard.html")) as fh:
        return fh.read()
