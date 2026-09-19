"""Structured logging setup. Quiet by default; opt in with configure_logging()."""

from __future__ import annotations

import logging
import os

_CONFIGURED = False


def configure_logging(level: str | int | None = None) -> None:
    """Configure root logging once. Level from arg or REPO_INTEL_LOG env."""
    global _CONFIGURED
    if _CONFIGURED:
        if level is not None:
            logging.getLogger("repo_intel").setLevel(_coerce(level))
        return
    lvl = _coerce(level if level is not None else os.environ.get("REPO_INTEL_LOG", "WARNING"))
    logging.basicConfig(
        level=lvl,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    _CONFIGURED = True


def _coerce(level: str | int) -> int:
    if isinstance(level, int):
        return level
    return getattr(logging, str(level).upper(), logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"repo_intel.{name}")
