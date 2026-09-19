# Git Repository Intelligence (`repo-intel`)

AI-assisted repository analytics that evaluates software health from **Git
history**: churn, code ownership, commit intelligence, bug-proneness,
architectural drift, developer knowledge concentration, predictive risk and
release readiness.

**The LLM is optional.** Every health check, score and flag is computed
deterministically and is available on the **CLI** and in a **Plotly GUI**. A
local LLM (e.g. Qwen via Ollama) only adds a natural-language briefing; the
default provider is a no-op that returns a rule-based summary.

Stack: Python · Git · GitPython · PyDriller · FastAPI · Plotly · (optional local Qwen).

## Layout

```
repo_intel/
├── config.py              thresholds, weights, paths
├── extract/               raw Git → structured records
│   ├── git_loader.py      GitPython: repo, branches, tags
│   ├── driller.py         PyDriller: commit/file traversal → History
│   └── cache.py           sqlite (+ optional parquet) cache
├── metrics/               deterministic analytics (no AI)
│   ├── churn.py  ownership.py  bugproneness.py  drift.py
│   ├── knowledge.py  commit_intel.py  release.py
├── analysis/
│   ├── health_score.py    aggregate score + weighting
│   ├── flags.py           rule engine → risk flags
│   └── predict.py         trend / regression risk model
├── llm/                   OPTIONAL layer
│   ├── base.py            LLMProvider interface + rule-based fallback
│   ├── qwen_local.py      local Qwen (Ollama / OpenAI-compatible)
│   ├── null_provider.py   no-op default
│   └── prompts.py
├── report/
│   ├── builder.py         unified result object
│   ├── exporters.py       json / md / html / csv
│   └── charts.py          Plotly figure builders
├── cli/main.py            command surface
└── api/                   FastAPI app + GUI
    ├── server.py  routes.py  static/ (dashboard + vendored plotly.js)
```

## Install

```bash
pip install -r requirements.txt
pip install -e .            # provides the `repo-intel` command
```

## CLI — everything without an LLM

```bash
repo-intel analyze   /repo              # overview + flags
repo-intel health    /repo              # health score 0–100
repo-intel hotspots  /repo -n 15        # bug-prone modules
repo-intel busfactor /repo              # knowledge concentration / silos
repo-intel drift     /repo              # architectural coupling
repo-intel readiness /repo              # release readiness verdict
repo-intel predict   /repo              # trend / regression risk
repo-intel departure /repo              # author departure / truck-factor risk
repo-intel authors   /repo              # contribution breakdown
repo-intel flags     /repo              # raised risk flags
repo-intel analyze   /repo -o report.html   # export json | md | html | csv (by extension)
```

Options: `--since-days N`, `--branch NAME`, `--max-commits N`, `--cache`
(sqlite/parquet reuse).

## GUI — Plotly dashboard

```bash
repo-intel serve /repo          # http://127.0.0.1:8000
```

KPIs (incl. predicted trend and tracked bug-fixes), commit-activity trend, risk
ranking, author donut, churn-vs-fixes scatter, and tables for flags, hotspots,
author departure risk, silos and drift. Light/dark toggle, time-window filter,
JSON export, loading/error states, and a click-through drill-down on any hotspot
showing its risk-signal breakdown.
JSON API: `/api/report`, `/api/hotspots`, `/api/busfactor`, `/api/departure`, `/api/drift`,
`/api/readiness`, `/api/predict`, `/api/flags`, `/api/authors`, `/api/activity`,
`/api/summary?llm=true`, `POST /api/refresh`.

## Optional local LLM (Qwen)

Narrative only — never required. `NullProvider` is the default.

```bash
ollama run qwen2.5:3b-instruct
repo-intel summary /repo --llm          # falls back to rule-based if unreachable

# or OpenAI-compatible (LM Studio / vLLM / llama.cpp):
export REPO_INTEL_LLM_BACKEND=openai
export REPO_INTEL_LLM_URL=http://localhost:1234
export REPO_INTEL_LLM_MODEL=qwen2.5-7b-instruct
```

| Env var | Default | Meaning |
|---|---|---|
| `REPO_INTEL_LLM_BACKEND` | `auto` | `ollama` \| `openai` \| `none` \| `auto` |
| `REPO_INTEL_LLM_URL` | `http://localhost:11434` | backend base URL |
| `REPO_INTEL_LLM_MODEL` | `qwen2.5:3b-instruct` | model name |

## Scale & robustness

```bash
repo-intel analyze /repo --jobs 8          # parallel mining (isolated worker clones)
repo-intel analyze /repo --incremental     # drill only new commits on top of the cache
repo-intel analyze /repo --timeout 120     # abort mining after N seconds
repo-intel analyze /repo --skip-merges -v  # ignore merge commits, INFO logging
```

Parallel mining is result-identical to a serial run (verified in
`tests/test_hardening.py`). Bad inputs raise typed errors
(`NotAGitRepositoryError`, `EmptyRepositoryError`, `MiningTimeoutError`) instead
of stack traces; binary files, merge/giant commits and shallow clones are handled.

## Deployment

```bash
docker compose up                          # dashboard on :8000, mounts $REPO_PATH
docker compose --profile llm up            # also start a local Ollama (Qwen)
```

The image is multi-stage and runs as a non-root user; deps are pinned in
`constraints.txt`. API hardening is opt-in via env vars (see `SECURITY.md`):

| Env var | Default | Effect |
|---|---|---|
| `REPO_INTEL_API_TOKEN` | unset | require `Authorization: Bearer <token>` on `/api/*` |
| `REPO_INTEL_CORS_ORIGINS` | none | browser origin allowlist |
| `REPO_INTEL_RATE_LIMIT` | 120 | per-IP requests/min (0 = off) |
| `REPO_INTEL_MAX_BODY` | 1 MiB | request body cap |

Ops endpoints: `GET /healthz` (liveness), `GET /readyz` (503 until first mine).

## Persistent storage

Mined reports are persisted (gzip-compressed JSON in a single sqlite file under
the data dir), so the server survives restarts without re-mining and multiple
projects can be managed side by side. Clearing is per repo/project.

```bash
repo-intel serve /repo           # loads a stored report if present (add --fresh to re-mine)
repo-intel store list            # every persisted project + head/health
repo-intel store clear /repo     # clear one project (stored report + mining cache)
repo-intel store clear --all     # wipe everything
```

API: `POST /api/clear` (clear this repo), `GET /api/store` (list projects); the
dashboard has a **Clear** button. Storage lives at `<REPO_INTEL_DATA>/store.sqlite`
(default `./data`).

## Multi-repo (multi-tenant) serving

One server can serve many repositories at once — each is a *project* keyed by its
path, mined under a per-project lock and cached/persisted independently, so
different projects (and users) are served concurrently.

```bash
# register another repo (mined and served alongside the default one)
curl -X POST 'http://127.0.0.1:8000/api/projects?repo=/path/to/other'
curl 'http://127.0.0.1:8000/api/projects'                    # list all projects
curl 'http://127.0.0.1:8000/api/report?project=<key-or-path>'# any endpoint takes ?project=
curl -X POST 'http://127.0.0.1:8000/api/clear?project=<key>' # clear just that project
```

## Complexity over history

Complexity is tracked as a **trend** (like churn), not just at HEAD — mean
cyclomatic complexity is sampled across history by reading each commit's tree
(no checkout):

```bash
repo-intel complexity /repo           # current hotspots + history trend table
repo-intel serve /repo --cx-trend     # dashboard shows the trend chart
```

`GET /api/complexity-trend` returns the series. See **BENCHMARKS.md** for
performance (throughput, parallel speedup, memory) up to 100k commits.

## Configuration file

Settings resolve as **`--config` file → `repo-intel.toml` in the repo → defaults**.
Any `Config` field can be overridden (under `[tool.repo-intel]`, `[repo-intel]`, or
bare keys):

```toml
[tool.repo-intel]
hotspot_risk = 55            # risk threshold for the high-risk flag
silo_owner_share = 0.75      # ownership share that marks a knowledge silo
readiness_window_days = 14
skip_merges = true
```

## Metrics (all deterministic, explainable)

- **Churn** — insertions+deletions per file, log-normalized.
- **Ownership / bus factor** — per-file author distribution; min authors for 50%
  of commits; ≥80% single-owner ⇒ *knowledge silo*.
- **Author departure risk** — per-author truck factor: how many files they solely
  own and what share of the codebase leaves with them.
- **Cyclomatic complexity (multi-language)** — static complexity of current source
  via lizard (optional; `pip install '.[complexity]'`), covering ~27 languages
  (Python, JS/TS, Java, Go, Rust, C/C++, Ruby, PHP, Kotlin, Swift, Scala, …),
  shown per hotspot with its detected language.
- **Issue-tracker linkage** — commits citing `#123` / `KEY-123`, distinguishing
  tracked defects from keyword-only bug-fix guesses (`tracked_bugfixes`).
- **Bug-proneness (0–100)** — weighted churn (.35), bug-fix ratio (.30),
  recency (.20), ownership (.15); weights in `config.py`.
- **Architectural drift** — temporal coupling (co-change confidence); cross-module flagged.
- **Predictive risk** — least-squares trend on monthly bug-fix rate & churn.
- **Release readiness (0–100)** — recent-window penalties → READY/CAUTION/NOT READY.
- **Health score** — blends readiness, high-risk density, silo density.

## Quality gates

CI (`.github/workflows/ci.yml`) runs on Python 3.9 / 3.11 / 3.12:

| Gate | Tool | Status |
|---|---|---|
| Lint | `ruff` | clean |
| Format | `black --check` | clean |
| Types | `mypy` (no implicit Optional) | clean |
| Tests | `pytest` | 50 tests |
| Coverage | `pytest-cov` | ~91% (gate ≥85%) |

Run everything locally:

```bash
pip install -e ".[dev]"
make all          # ruff + black + mypy + pytest --cov
```

- **Typed schema** — every report is validated against Pydantic v2 models
  (`repo_intel/models.py`); the API serves a typed OpenAPI schema at `/openapi.json`.
- **Risk-model back-test** — `tests/test_risk_validation.py` synthesizes a repo with
  labeled buggy vs clean modules and asserts precision@3 and score separation, so the
  scoring weights are measured, not just asserted.
- **Layer coverage** — extract (fixture repo), cache round-trip, exporters, API
  (`TestClient`), CLI, and LLM providers (mocked) are all tested.
- `pre-commit` hooks in `.pre-commit-config.yaml`.
