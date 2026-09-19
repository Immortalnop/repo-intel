"""Cache layer: sqlite round-trip fidelity."""

from repo_intel.extract import cache, driller


def test_cache_roundtrip(demo_repo, tmp_path, monkeypatch):
    # redirect cache dir into tmp so tests don't pollute the repo
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path / "cache")

    hist = driller.drill(demo_repo)
    db = cache.save(hist)
    assert db.exists()

    loaded = cache.load(demo_repo)
    assert loaded is not None
    assert len(loaded.commits) == len(hist.commits)
    assert set(loaded.files) == set(hist.files)
    assert loaded.files["core/engine.py"].churn == hist.files["core/engine.py"].churn
    assert dict(loaded.authors) == dict(hist.authors)


def test_cache_miss_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path / "cache")
    assert cache.load("/nonexistent/repo/path") is None
