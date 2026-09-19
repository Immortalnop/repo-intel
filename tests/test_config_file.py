"""Tier 4: TOML config-file loading and precedence."""

from repo_intel.config import Config


def test_from_file_tool_table(tmp_path):
    p = tmp_path / "repo-intel.toml"
    p.write_text("[tool.repo-intel]\nhotspot_risk = 42.0\nskip_merges = true\n")
    c = Config.from_file(p)
    assert c.hotspot_risk == 42.0
    assert c.skip_merges is True


def test_from_file_bare_table(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text("readiness_window_days = 14\n")
    assert Config.from_file(p).readiness_window_days == 14


def test_from_file_ignores_unknown_keys(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text("[repo-intel]\nnot_a_field = 1\nsilo_min_commits = 7\n")
    c = Config.from_file(p)
    assert c.silo_min_commits == 7
    assert not hasattr(c, "not_a_field")


def test_resolve_precedence(tmp_path):
    # repo-local toml is picked up when no explicit path is given
    (tmp_path / "repo-intel.toml").write_text("[tool.repo-intel]\nhotspot_risk = 33.0\n")
    assert Config.resolve(repo=str(tmp_path)).hotspot_risk == 33.0
    # explicit config wins
    other = tmp_path / "other.toml"
    other.write_text("hotspot_risk = 99.0\n")
    assert Config.resolve(config_path=str(other), repo=str(tmp_path)).hotspot_risk == 99.0
    # default when nothing provided
    assert Config.resolve().hotspot_risk == 60.0
