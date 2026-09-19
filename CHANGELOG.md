# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/) and the
project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- **Multi-tenant API**: one server can register and serve many repositories
  concurrently (`ProjectRegistry`, per-project mining locks, threadpool). New
  `POST/GET /api/projects`, and every data endpoint accepts `?project=`. The
  default single-repo behavior is unchanged.
- **Complexity trend over history**: `complexity` CLI command, `serve --cx-trend`,
  `/api/complexity-trend`, and a dashboard chart — mean cyclomatic complexity at
  sampled commits (read from git trees, no checkout).
- **Performance benchmarks**: `benchmarks/genrepo.py` + `benchmarks/bench.py` and
  measured results in `BENCHMARKS.md` (100k commits mined in 467 s / 214 c/s,
  RSS 193 MB; memory scales linearly).

### Added
- **Multi-language complexity**: cyclomatic complexity now uses lizard (~27
  languages) instead of Python-only radon; each hotspot shows its language.
- **Persistent storage**: mined reports are stored (gzip + sqlite) and survive
  restarts; `serve` loads a stored report unless `--fresh`. Managed per project
  via `store list` / `store clear [repo|--all]`, `POST /api/clear`,
  `GET /api/store`, and a dashboard **Clear** button.

### Added (Tier 4 — depth & polish)
- **Metrics**: cyclomatic complexity via radon (optional), author departure /
  truck-factor risk (`departure` command, `/api/departure`), and issue-tracker
  linkage (`tracked_bugfixes`, `issue_linked_ratio`).
- **Config files**: `repo-intel.toml` support with precedence
  `--config → repo-local → defaults` (`Config.resolve`).
- **LLM**: `CachingProvider` (memoizes narratives by report signature), a prompt
  token budget, and `get_provider(cache=...)` composition.
- **GUI**: light/dark theme toggle, loading + error states, JSON export, a
  time-window filter, and a hotspot drill-down modal with the risk-signal
  breakdown.

### Added
- **Robustness**: typed exceptions (`NotAGitRepositoryError`, `EmptyRepositoryError`,
  `MiningTimeoutError`, `DependencyMissingError`); safe handling of binary files,
  merge commits (`--skip-merges`), giant commits, and shallow-clone warnings.
- **Scale**: parallel mining (`--jobs N`, isolated per-worker clones — result is
  identical to a serial mine) and incremental mining (`--incremental`, drills only
  new commits on top of the cache).
- **Ops**: structured logging (`--verbose`, `REPO_INTEL_LOG`), mining progress, and
  a mining `--timeout`.
- **API hardening**: `/healthz`, `/readyz`; optional bearer auth
  (`REPO_INTEL_API_TOKEN`); configurable CORS; per-IP rate limiting; request
  body-size cap.
- **Deployment**: multi-stage non-root `Dockerfile`, `docker-compose.yml` with an
  optional Ollama profile, and pinned `constraints.txt`.
- Docs: `CONTRIBUTING.md`, `SECURITY.md`, PEP 561 `py.typed` marker.

## [1.0.0]

### Added
- Layered analytics package (`extract`, `metrics`, `analysis`, `llm`, `report`,
  `cli`, `api`) with deterministic churn, ownership, bug-proneness, drift,
  knowledge-concentration, predictive-risk and release-readiness metrics.
- CLI, FastAPI backend and Plotly dashboard; JSON/MD/HTML/CSV exporters.
- Optional local Qwen narrative with a rule-based fallback.
- Pydantic v2 schema, CI (ruff/black/mypy/pytest), ~91% coverage, risk-model
  back-test.
