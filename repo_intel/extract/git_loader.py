"""GitPython layer: open a repo and read its high-level structure
(branches, tags, HEAD, remotes). Used for context and release analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field

try:
    from git import Repo

    _HAVE_GIT = True
except Exception:  # pragma: no cover
    _HAVE_GIT = False


@dataclass
class RepoInfo:
    path: str
    head: str | None = None
    active_branch: str | None = None
    branches: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    remotes: list[str] = field(default_factory=list)
    is_dirty: bool = False


def load_repo_info(path: str) -> RepoInfo:
    """Return branches/tags/HEAD for `path`. Degrades gracefully."""
    if not _HAVE_GIT:
        return RepoInfo(path=path)
    try:
        repo = Repo(path, search_parent_directories=True)
        try:
            active = repo.active_branch.name
        except Exception:
            active = None  # detached HEAD
        return RepoInfo(
            path=path,
            head=repo.head.commit.hexsha[:10] if repo.head.is_valid() else None,
            active_branch=active,
            branches=[b.name for b in repo.branches],
            tags=sorted(t.name for t in repo.tags),
            remotes=[r.name for r in repo.remotes],
            is_dirty=repo.is_dirty(),
        )
    except Exception:
        return RepoInfo(path=path)
