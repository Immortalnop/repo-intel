"""Extract layer: PyDriller mining + GitPython repo info + excludes."""

from repo_intel.config import Config
from repo_intel.extract import driller, git_loader


def test_drill_basic(demo_repo):
    hist = driller.drill(demo_repo)
    assert hist.repo == demo_repo
    assert len(hist.commits) == 21
    assert {"Alice", "Bob", "Carol"} <= set(hist.authors)
    assert "core/engine.py" in hist.files
    assert hist.files["core/engine.py"].commits >= 12


def test_bugfix_detection(demo_repo):
    hist = driller.drill(demo_repo)
    assert sum(1 for c in hist.commits if c["is_bugfix"]) > 0
    assert hist.files["core/engine.py"].bugfixes > 0


def test_cochange_recorded(demo_repo):
    hist = driller.drill(demo_repo)
    key = tuple(sorted(("api/routes.py", "core/engine.py")))
    assert hist.cochange.get(key, 0) >= 3


def test_excludes_applied(demo_repo):
    cfg = Config()
    cfg.excludes = ["core/*"]
    hist = driller.drill(demo_repo, cfg=cfg)
    assert not any(p.startswith("core/") for p in hist.files)


def test_max_commits_cap(demo_repo):
    hist = driller.drill(demo_repo, max_commits=5)
    assert len(hist.commits) == 5


def test_git_loader(demo_repo):
    info = git_loader.load_repo_info(demo_repo)
    assert info.head is not None
    assert info.active_branch in ("main", "master")


def test_git_loader_missing_repo(tmp_path):
    info = git_loader.load_repo_info(str(tmp_path))  # not a git repo
    assert info.head is None  # degrades gracefully
