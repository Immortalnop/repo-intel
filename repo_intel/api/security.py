"""API hardening: optional bearer auth, rate limiting, body-size cap, CORS.

All are configured via environment variables and are opt-in, so local use stays
frictionless while a deployed instance can be locked down:

  REPO_INTEL_API_TOKEN    if set, /api/* requires `Authorization: Bearer <token>`
  REPO_INTEL_CORS_ORIGINS comma-separated allowed origins (default: none)
  REPO_INTEL_RATE_LIMIT   requests/minute per client IP (default 120; 0=off)
  REPO_INTEL_MAX_BODY     max request body bytes (default 1048576)
"""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..logging_utils import get_logger

log = get_logger("api.security")

_PROTECTED_PREFIX = "/api"
_OPEN_PATHS = {"/healthz", "/readyz"}


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def configure_security(app: FastAPI) -> None:
    origins = [
        o.strip() for o in os.environ.get("REPO_INTEL_CORS_ORIGINS", "").split(",") if o.strip()
    ]
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["GET", "POST"],
            allow_headers=["*"],
        )

    max_body = _int_env("REPO_INTEL_MAX_BODY", 1_048_576)
    rate_limit = _int_env("REPO_INTEL_RATE_LIMIT", 120)
    hits: dict[str, deque[float]] = defaultdict(deque)

    @app.middleware("http")
    async def _guard(request: Request, call_next):
        path = request.url.path

        # body-size cap
        cl = request.headers.get("content-length")
        if cl and cl.isdigit() and int(cl) > max_body:
            return JSONResponse({"detail": "Request body too large"}, status_code=413)

        # rate limit (per client IP, sliding 60s window)
        if rate_limit > 0 and path.startswith(_PROTECTED_PREFIX):
            ip = request.client.host if request.client else "unknown"
            now = time.monotonic()
            q = hits[ip]
            while q and now - q[0] > 60:
                q.popleft()
            if len(q) >= rate_limit:
                return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)
            q.append(now)

        # bearer auth
        token = os.environ.get("REPO_INTEL_API_TOKEN")
        if token and path.startswith(_PROTECTED_PREFIX) and path not in _OPEN_PATHS:
            auth = request.headers.get("authorization", "")
            if auth != f"Bearer {token}":
                return JSONResponse({"detail": "Unauthorized"}, status_code=401)

        return await call_next(request)
