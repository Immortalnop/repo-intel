"""Exporters: json / md / csv / html."""

import json

import pytest

from repo_intel.report import exporters


def test_json_export(report, tmp_path):
    p = tmp_path / "r.json"
    exporters.export(report, "json", str(p))
    data = json.loads(p.read_text())
    assert data["summary"]["files"] == 3


def test_markdown_export(report, tmp_path):
    p = tmp_path / "r.md"
    out = exporters.export(report, "md", str(p))
    assert "# Repository Intelligence" in out
    assert "core/engine.py" in out
    assert p.exists()


def test_csv_export(report, tmp_path):
    p = tmp_path / "r.csv"
    out = exporters.export(report, "csv", str(p))
    lines = out.strip().splitlines()
    assert lines[0].startswith("path,commits,churn")
    assert len(lines) == 1 + len(report["all_files"])


def test_html_export_selfcontained(report, tmp_path):
    p = tmp_path / "r.html"
    out = exporters.export(report, "html", str(p))
    assert out.lstrip().lower().startswith("<!doctype html>")
    assert "plotly" in out.lower()  # figures embedded


def test_unknown_format_raises(report):
    with pytest.raises(ValueError):
        exporters.export(report, "xml", "x.xml")
