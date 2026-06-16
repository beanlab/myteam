from __future__ import annotations

from pathlib import Path


def test_load_markdown_skill_prints_body_without_frontmatter(run_myteam, tmp_path: Path) -> None:
    skill = tmp_path / "skill.md"
    skill.write_text("---\ntype: skill\ndescription: demo\n---\n\nUse the skill.\n", encoding="utf-8")

    result = run_myteam(tmp_path, "load", "skill.md")

    assert result.exit_code == 0
    assert result.stdout == "\nUse the skill.\n"
    assert result.stderr == ""


def test_load_markdown_skill_does_not_require_valid_frontmatter(run_myteam, tmp_path: Path) -> None:
    skill = tmp_path / "loose.md"
    skill.write_text("Just content.\n", encoding="utf-8")

    result = run_myteam(tmp_path, "load", "loose.md")

    assert result.exit_code == 0
    assert result.stdout == "Just content.\n"


def test_load_python_skill_uses_runtime_environment(run_myteam, tmp_path: Path, monkeypatch) -> None:
    skill = tmp_path / "skill.py"
    skill.write_text(
        "import os\n"
        "import sys\n"
        "from pathlib import Path\n"
        "print(f'executable={Path(sys.executable).name}')\n"
        "print(f'cwd-marker={Path(\"cwd-marker.txt\").read_text(encoding=\"utf-8\").strip()}')\n"
        "print(f'env-marker={os.environ[\"MYTEAM_TEST_MARKER\"]}')\n"
        "print(f'argv-count={len(sys.argv)}')\n",
        encoding="utf-8",
    )
    (tmp_path / "cwd-marker.txt").write_text("from cwd\n", encoding="utf-8")
    monkeypatch.setenv("MYTEAM_TEST_MARKER", "from env")

    result = run_myteam(tmp_path, "load", "skill.py")

    assert result.exit_code == 0
    assert "executable=python" in result.stdout
    assert "cwd-marker=from cwd" in result.stdout
    assert "env-marker=from env" in result.stdout
    assert "argv-count=1" in result.stdout


def test_load_python_skill_failure_prints_stderr_and_omits_stdout(run_myteam, tmp_path: Path) -> None:
    skill = tmp_path / "broken.py"
    skill.write_text(
        "import sys\n"
        "print('hidden stdout')\n"
        "print('visible stderr', file=sys.stderr)\n"
        "sys.exit(7)\n",
        encoding="utf-8",
    )

    result = run_myteam(tmp_path, "load", "broken.py")

    assert result.exit_code == 7
    assert "visible stderr" in result.stderr
    assert "hidden stdout" not in result.stdout


def test_load_folder_and_unsupported_extension_fail_clearly(run_myteam, tmp_path: Path) -> None:
    folder = tmp_path / "skills"
    folder.mkdir()
    unsupported = tmp_path / "skill.txt"
    unsupported.write_text("content\n", encoding="utf-8")

    folder_result = run_myteam(tmp_path, "load", "skills")
    unsupported_result = run_myteam(tmp_path, "load", "skill.txt")

    assert folder_result.exit_code == 1
    assert "Use 'myteam list skills'" in folder_result.stderr
    assert unsupported_result.exit_code == 1
    assert "unsupported extension" in unsupported_result.stderr
