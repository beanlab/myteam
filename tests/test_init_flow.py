from __future__ import annotations

from pathlib import Path


def test_init_creates_root_agent_system(run_myteam, tmp_path: Path):
    result = run_myteam(tmp_path, "init")

    assert result.exit_code == 0
    assert (tmp_path / "AGENTS.md").exists()
    assert (tmp_path / ".myteam" / "role.md").exists()
    assert (tmp_path / ".myteam" / "load.py").exists()
    assert (tmp_path / ".myteam" / ".myteam-version").exists()
    assert not (tmp_path / ".myteam" / "myteam").exists()


def test_init_preserves_existing_agents_md(run_myteam, tmp_path: Path):
    agents_md = tmp_path / "AGENTS.md"
    agents_md.write_text("custom agents instructions\n", encoding="utf-8")

    result = run_myteam(tmp_path, "init")

    assert result.exit_code == 0
    assert agents_md.read_text(encoding="utf-8") == "custom agents instructions\n"


def test_init_accepts_custom_prefix(run_myteam, tmp_path: Path):
    result = run_myteam(tmp_path, "init", "--prefix", ".agents")

    assert result.exit_code == 0
    assert (tmp_path / "AGENTS.md").exists()
    assert (tmp_path / ".agents" / "role.md").exists()
    assert (tmp_path / ".agents" / "load.py").exists()
    assert (tmp_path / ".agents" / ".myteam-version").exists()
    assert not (tmp_path / ".myteam").exists()


def test_get_role_succeeds_after_init(run_myteam, initialized_project: Path):
    result = run_myteam(initialized_project, "get", "role")

    assert result.exit_code == 0
    assert "# Skills" in result.stdout
    assert "# Tools" in result.stdout
    assert "# Roles" in result.stdout
    assert result.stdout.index("# Skills") < result.stdout.index("# Tools") < result.stdout.index("# Roles")


def test_get_role_succeeds_after_init_with_custom_prefix(run_myteam, tmp_path: Path):
    init_result = run_myteam(tmp_path, "init", "--prefix", ".agents")
    assert init_result.exit_code == 0

    result = run_myteam(tmp_path, "get", "role", "--prefix", ".agents")

    assert result.exit_code == 0
    assert "# Skills" in result.stdout
    assert "# Tools" in result.stdout
    assert "# Roles" in result.stdout
    assert result.stdout.index("# Skills") < result.stdout.index("# Tools") < result.stdout.index("# Roles")
