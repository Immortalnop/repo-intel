"""Report builder + schema validation + findings correctness."""

import json

from repo_intel.models import Report


def test_report_schema_valid(report):
    Report.model_validate(report)  # raises on violation


def test_summary_bounds(report):
    s = report["summary"]
    assert 0 <= s["health_score"] <= 100
    assert s["commits"] == 21
    assert s["files"] == 3
    assert s["authors"] == 3


def test_hotspot_is_engine(report):
    assert report["hotspots"][0]["path"] == "core/engine.py"
    assert report["hotspots"][0]["risk_score"] >= 60


def test_knowledge_silo_detected(report):
    silos = {s["path"]: s for s in report["knowledge_silos"]}
    assert "utils/helpers.py" in silos
    assert silos["utils/helpers.py"]["top_author"] == "Bob"
    assert silos["utils/helpers.py"]["bus_factor"] == 1


def test_cross_module_drift_flagged(report):
    assert any(c["cross_module"] for c in report["coupling"])
    codes = {f["code"] for f in report["flags"]}
    assert "ARCHITECTURAL_DRIFT" in codes


def test_report_json_serializable(report):
    json.dumps(report, default=str)  # must not raise
