# Contributing

## Setup

```bash
pip install -e ".[dev]"
pre-commit install
```

## Before you push

```bash
make all      # ruff + black + mypy + pytest --cov (gate >=85%)
```

CI runs the same gates on Python 3.9 / 3.11 / 3.12. PRs must be green.

## Conventions

- **Layering**: `extract → metrics → analysis → report → {cli, api}`. Metrics and
  analysis are pure and AI-free; the `llm` layer is optional and defaults to a
  no-op provider. Keep dependencies pointing one way.
- **Types**: full type hints; `mypy` runs with `no_implicit_optional`.
- **Schema**: any change to the report shape must update `repo_intel/models.py`
  and the tests that validate against it.
- **Tests**: new behavior needs a test. Deterministic fixtures build real git
  repos via `tests/conftest.py` — no network, no mocks for Git itself.
- **Config**: new tunables go in `repo_intel/config.py`, not scattered constants.

## Versioning

Semantic Versioning. Update `CHANGELOG.md` under *Unreleased*; bump the version in
`pyproject.toml` and `repo_intel/__init__.py` on release.
