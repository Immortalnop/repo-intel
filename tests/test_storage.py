"""Persistent report store + per-repo cache clearing."""

from repo_intel.extract import cache, driller
from repo_intel.storage import ReportStore, project_key, purge


def test_store_roundtrip(report, tmp_path):
    s = ReportStore(tmp_path / "store.sqlite")
    s.put(report["repo"], report)
    got = s.get(report["repo"])
    assert got is not None
    assert got["summary"]["health_score"] == report["summary"]["health_score"]
    assert got["hotspots"][0]["path"] == report["hotspots"][0]["path"]


def test_store_list_and_meta(report, tmp_path):
    s = ReportStore(tmp_path / "store.sqlite")
    s.put(report["repo"], report)
    rows = s.list()
    assert len(rows) == 1
    assert rows[0].n_commits == report["summary"]["commits"]
    assert rows[0].health == report["summary"]["health_score"]


def test_store_delete_and_clear(report, tmp_path):
    s = ReportStore(tmp_path / "store.sqlite")
    s.put(report["repo"], report)
    assert s.delete(report["repo"]) is True
    assert s.get(report["repo"]) is None
    assert s.delete(report["repo"]) is False  # already gone
    s.put(report["repo"], report)
    assert s.clear_all() == 1


def test_project_key_stable_and_distinct(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    assert project_key(str(a)) == project_key(str(a))
    assert project_key(str(a)) != project_key(str(b))


def test_cache_clear_by_repo(demo_repo, tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path / "cache")
    hist = driller.drill(demo_repo)
    cache.save(hist)
    assert list((tmp_path / "cache").glob("*.sqlite"))
    removed = cache.clear(demo_repo)
    assert removed >= 1
    assert not list((tmp_path / "cache").glob("*.sqlite"))


def test_purge_clears_report_and_cache(report, demo_repo, tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path / "cache")
    store = ReportStore(tmp_path / "store.sqlite")
    store.put(demo_repo, report)
    hist = driller.drill(demo_repo)
    cache.save(hist)
    res = purge(demo_repo, store=store)
    assert res["report_removed"] is True
    assert res["cache_files_removed"] >= 1
    assert store.get(demo_repo) is None
