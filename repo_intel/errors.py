"""Typed exceptions so callers get clear messages, not stack traces."""

from __future__ import annotations


class RepoIntelError(Exception):
    """Base class for all repo-intel errors."""


class NotAGitRepositoryError(RepoIntelError):
    """The given path is not a Git repository."""


class EmptyRepositoryError(RepoIntelError):
    """The repository has no commits (or none in the selected range)."""


class MiningTimeoutError(RepoIntelError):
    """Mining exceeded the configured time budget."""


class DependencyMissingError(RepoIntelError):
    """A required optional dependency (e.g. PyDriller) is not installed."""
