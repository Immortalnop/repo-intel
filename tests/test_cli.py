"""CLI surface via main() with captured stdout."""

import json

import pytest

from repo_intel.cli.main import main


def test_health_cmd(demo_repo, capsys):
    main(["health", demo_repo])
    out = capsys.readouterr().out
    assert "/100" in out


def test_hotspots_cmd(demo_repo, capsys):
    main(["hotspots", demo_repo, "-n", "3"])
    out = capsys.readouterr().out
    assert "engine.py" in out


def test_flags_cmd(demo_repo, capsys):
    main(["flags", demo_repo])
    out = capsys.readouterr().out
    assert "BUG_PRONE_MODULE" in out


def test_predict_cmd(demo_repo, capsys):
    main(["predict", demo_repo])
    out = capsys.readouterr().out
    assert "trend" in out


def test_summary_cmd_fallback(demo_repo, capsys):
    main(["summary", demo_repo])
    out = capsys.readouterr().out
    assert "fallback" in out


def test_analyze_export(demo_repo, tmp_path, capsys):
    out_file = tmp_path / "r.json"
    main(["analyze", demo_repo, "-o", str(out_file)])
    assert out_file.exists()
    assert json.loads(out_file.read_text())["summary"]["files"] == 3


def test_bad_repo_exits_nonzero(tmp_path):
    with pytest.raises(SystemExit) as e:
        main(["health", str(tmp_path)])  # not a git repo -> error exit
    assert e.value.code == 1
