# Security

## Threat model

`repo-intel` reads a Git repository and serves analytics. It never executes
repository code; it only parses history metadata. The main exposure is the HTTP
server if you deploy it beyond localhost.

## Hardening the API

The dashboard/API is unauthenticated and bound to `127.0.0.1` by default. Before
exposing it, set:

| Env var | Effect |
|---|---|
| `REPO_INTEL_API_TOKEN` | require `Authorization: Bearer <token>` on `/api/*` |
| `REPO_INTEL_CORS_ORIGINS` | allowlist browser origins (default: none) |
| `REPO_INTEL_RATE_LIMIT` | per-IP requests/minute (default 120; 0 disables) |
| `REPO_INTEL_MAX_BODY` | max request body bytes (default 1 MiB) |

`/healthz` and `/readyz` stay open for load balancers.

The analyzed repository path is set by the operator at launch (`serve /repo`), not
by API clients, so untrusted callers cannot point the server at arbitrary paths.

## Reporting a vulnerability

Open a private security advisory or email the maintainers. Please do not file a
public issue for undisclosed vulnerabilities.
