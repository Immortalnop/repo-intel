"""FastAPI app assembly + serve()."""

from __future__ import annotations

from fastapi import FastAPI

from . import routes
from .security import configure_security

app = FastAPI(title="Git Repository Intelligence", version="1.0.0")
configure_security(app)
app.include_router(routes.router)


def serve(
    repo: str = ".",
    host: str = "127.0.0.1",
    port: int = 8000,
    since_days: int | None = None,
    max_commits: int | None = None,
    fresh: bool = False,
    cx_trend: bool = False,
):
    import uvicorn

    from ..storage import DEFAULT_STORE

    routes.STATE.update(
        repo=repo, since_days=since_days, max_commits=max_commits, report=None, cx_trend=cx_trend
    )
    stored = None if fresh else DEFAULT_STORE.get(repo)
    if stored is not None:
        routes.STATE["report"] = stored
        s = stored["summary"]
        print(
            f"Loaded stored report: {s['commits']} commits, {s['files']} files "
            f"(use --fresh or Re-mine to refresh)."
        )
    else:
        print(f"Mining {repo} ...")
        routes.mine()
        s = routes.STATE["report"]["summary"]
        print(f"Done: {s['commits']} commits, {s['files']} files.")
    print(f"Dashboard -> http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="warning")
