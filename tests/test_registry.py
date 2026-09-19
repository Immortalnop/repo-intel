"""Multi-tenant registry: many repos, isolation, concurrency, per-project clear."""

import concurrent.futures
import os
import subprocess

import pytest

from repo_intel.registry import ProjectRegistry
from repo_intel.storage import ReportStore, project_key


def _tiny_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Z",
        "GIT_AUTHOR_EMAIL": "z@x.com",
        "GIT_COMMITTER_NAME": "Z",
        "GIT_COMMITTER_EMAIL": "z@x.com",
    }
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    (path / "x.py").write_text("def a():\n    return 1\n")
    subprocess.run(["git", "add", "-A"], cwd=path, check=True, env=env)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=path, check=True, env=env)
    return str(path)


@pytest.fixture
def registry(tmp_path):
    return ProjectRegistry(ReportStore(tmp_path / "store.sqlite"))


def test_register_and_serve_two_repos(demo_repo, tmp_path, registry):
    other = _tiny_repo(tmp_path / "other")
    k1 = registry.register(demo_repo)
    k2 = registry.register(other)
    assert k1 != k2
    r1 = registry.get_report(k1)
    r2 = registry.get_report(k2)
    assert r1["summary"]["commits"] == 21
    assert r2["summary"]["commits"] == 1
    assert {p["repo"] for p in registry.list()} == {demo_repo, other}


def test_concurrent_distinct_projects(demo_repo, tmp_path, registry):
    other = _tiny_repo(tmp_path / "other")
    keys = [registry.register(demo_repo), registry.register(other)]
    with concurrent.futures.ThreadPoolExecutor(2) as ex:
        results = list(ex.map(registry.get_report, keys))
    assert all(r is not None for r in results)
    assert {r["summary"]["commits"] for r in results} == {21, 1}


def test_report_cached_after_first_mine(demo_repo, registry):
    k = registry.register(demo_repo)
    first = registry.get_report(k)
    assert registry.get_report(k) is first  # same object -> served from memory


def test_clear_one_project_isolates_others(demo_repo, tmp_path, registry):
    other = _tiny_repo(tmp_path / "other")
    k1 = registry.register(demo_repo)
    k2 = registry.register(other)
    registry.get_report(k1)
    registry.get_report(k2)
    res = registry.clear(k1)
    assert res["report_removed"] is True
    # k2 still served
    assert registry.get_report(k2)["summary"]["commits"] == 1


def test_resolve_by_repo_path(demo_repo, registry):
    key = registry.resolve(repo=demo_repo)
    assert key == project_key(demo_repo)
