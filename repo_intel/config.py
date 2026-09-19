"""Central configuration: thresholds, weights and paths.

Every tunable lives here so metrics stay declarative and reproducible.
Values can be overridden via environment variables (REPO_INTEL_*) or by
passing a Config instance around.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field, fields
from pathlib import Path

# --- paths ---------------------------------------------------------------
DATA_DIR = Path(os.environ.get("REPO_INTEL_DATA", "data"))
CACHE_DIR = DATA_DIR / "cache"
REPORT_DIR = DATA_DIR / "reports"

# --- bug-fix commit detection -------------------------------------------
BUGFIX_PATTERN = re.compile(
    r"\b(fix(e[ds])?|bug|defect|issue|patch|hotfix|regression|crash|"
    r"error|fault|broken|revert|workaround)\b",
    re.IGNORECASE,
)

# --- issue-tracker references (GitHub #123, JIRA/Linear KEY-123) ---------
ISSUE_PATTERN = re.compile(r"(#\d+|\b[A-Z][A-Z0-9]+-\d+)\b")

# files ignored during mining (globs)
DEFAULT_EXCLUDES: list[str] = [
    "*.lock",
    "*.min.js",
    "*.map",
    "package-lock.json",
    "yarn.lock",
    "*.svg",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.pdf",
    "*.ico",
    "dist/*",
    "build/*",
    "node_modules/*",
    "vendor/*",
    "*.ipynb",
]


@dataclass
class Config:
    # risk-score signal weights (must sum to ~1.0)
    risk_weights: dict[str, float] = field(
        default_factory=lambda: {
            "churn": 0.35,
            "bugfix_ratio": 0.30,
            "recency": 0.20,
            "ownership": 0.15,
        }
    )
    # health-score component weights
    health_weights: dict[str, float] = field(
        default_factory=lambda: {
            "readiness": 0.45,
            "risk_density": 0.30,
            "silo_density": 0.25,
        }
    )
    recency_half_life_days: float = 90.0
    readiness_window_days: int = 30

    # thresholds
    silo_owner_share: float = 0.80  # >= => knowledge silo
    silo_min_commits: int = 3
    hotspot_risk: float = 60.0  # >= => high-risk flag
    coupling_min_shared: int = 3
    coupling_min_confidence: float = 0.50
    project_bus_factor_share: float = 0.60
    bus_factor_threshold: float = 0.50  # authors covering this share of commits

    excludes: list[str] = field(default_factory=lambda: list(DEFAULT_EXCLUDES))

    # mining behavior
    skip_merges: bool = False  # ignore merge commits
    max_commit_files: int = 1000  # skip giant commits (vendored drops, etc.)
    progress_every: int = 500  # log a progress line every N commits

    @classmethod
    def load(cls) -> Config:
        c = cls()
        if os.environ.get("REPO_INTEL_HALFLIFE"):
            c.recency_half_life_days = float(os.environ["REPO_INTEL_HALFLIFE"])
        if os.environ.get("REPO_INTEL_WINDOW"):
            c.readiness_window_days = int(os.environ["REPO_INTEL_WINDOW"])
        return c

    @classmethod
    def from_file(cls, path: str | Path) -> Config:
        """Load config from a TOML file, overlaid on env-derived defaults.

        Recognized keys mirror the dataclass fields, optionally under a
        [tool.repo-intel] or [repo-intel] table (so it can live in pyproject.toml).
        Unknown keys are ignored.
        """
        data = _read_toml(Path(path))
        table = (
            data.get("tool", {}).get("repo-intel")
            or data.get("repo-intel")
            or data.get("repo_intel")
            or data
        )
        c = cls.load()
        valid = {f.name for f in fields(cls)}
        for k, v in table.items():
            key = k.replace("-", "_")
            if key in valid:
                setattr(c, key, v)
        return c

    @classmethod
    def resolve(cls, config_path: str | None = None, repo: str | None = None) -> Config:
        """Config precedence: explicit --config > repo-intel.toml in repo > defaults."""
        if config_path:
            return cls.from_file(config_path)
        if repo:
            candidate = Path(repo) / "repo-intel.toml"
            if candidate.is_file():
                return cls.from_file(candidate)
        return cls.load()


def _read_toml(path: Path) -> dict:
    import sys

    if sys.version_info >= (3, 11):
        import tomllib
    else:  # pragma: no cover - exercised only on 3.9/3.10
        import tomli as tomllib
    with open(path, "rb") as fh:
        return tomllib.load(fh)


DEFAULT = Config.load()
