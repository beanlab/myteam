from __future__ import annotations

from pathlib import Path


def test_get_role_strips_frontmatter_and_lists_children(run_myteam, initialized_project: Path):
    role_dir = initialized_project / ".myteam" / "developer"
    role_dir.mkdir()
    (role_dir / "role.md").write_text(
        "---\nname: Developer\ndescription: Implements features\n---\n\nWrite the code.\n",
        encoding="utf-8",
    )
    (role_dir / "load.py").write_text(
        "#!/usr/bin/env python3\n"
        "from __future__ import annotations\n\n"
        "from pathlib import Path\n\n"
        "from myteam.utils import print_instructions, get_myteam_root, explain_skills, explain_roles, explain_tools, list_skills, list_roles, list_tools, print_directory_tree\n\n"
        "def main() -> int:\n"
        "    base = Path(__file__).resolve().parent\n"
        "    print('ROLE LOAD MARKER')\n"
        "    print_instructions(base)\n"
        "    myteam = get_myteam_root(base)\n"
        "    print_directory_tree(myteam.parent)\n"
        "    explain_roles()\n"
        "    list_roles(base, myteam, [])\n"
        "    explain_skills()\n"
        "    list_skills(base, myteam, [])\n"
        "    explain_tools()\n"
        "    list_tools(base, myteam, [])\n"
        "    return 0\n\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )

    child_role = role_dir / "frontend"
    child_role.mkdir()
    (child_role / "role.md").write_text("Frontend role\n", encoding="utf-8")
    (child_role / "load.py").write_text("print('frontend')\n", encoding="utf-8")

    child_skill = role_dir / "testing"
    child_skill.mkdir()
    (child_skill / "skill.md").write_text("Testing skill\n", encoding="utf-8")
    (child_skill / "load.py").write_text("print('testing')\n", encoding="utf-8")

    (role_dir / "helper.py").write_text("print('tool')\n", encoding="utf-8")

    result = run_myteam(initialized_project, "get", "role", "developer")

    assert result.exit_code == 0
    assert "ROLE LOAD MARKER" in result.stdout
    assert "Write the code." in result.stdout
    assert "name: Developer" not in result.stdout
    assert "developer/frontend" in result.stdout
    assert "developer/testing" in result.stdout
    assert "helper.py" in result.stdout


def test_get_skill_strips_frontmatter_and_lists_children(run_myteam, initialized_project: Path):
    skill_dir = initialized_project / ".myteam" / "python"
    skill_dir.mkdir()
    (skill_dir / "skill.md").write_text(
        "---\nname: Python\ndescription: Python guidance\n---\n\nUse Python.\n",
        encoding="utf-8",
    )
    (skill_dir / "load.py").write_text(
        "#!/usr/bin/env python3\nfrom __future__ import annotations\n\n"
        "from pathlib import Path\n\n"
        "from myteam.utils import print_instructions, get_myteam_root, list_roles, list_skills, list_tools\n\n"
        "def main() -> int:\n"
        "    base = Path(__file__).resolve().parent\n"
        "    print('SKILL LOAD MARKER')\n"
        "    print_instructions(base)\n"
        "    myteam = get_myteam_root(base)\n"
        "    list_roles(base, myteam, [])\n"
        "    list_skills(base, myteam, [])\n"
        "    list_tools(base, myteam, [])\n"
        "    return 0\n\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )

    nested_skill = skill_dir / "testing"
    nested_skill.mkdir()
    (nested_skill / "skill.md").write_text("Nested testing skill\n", encoding="utf-8")
    (nested_skill / "load.py").write_text("print('nested')\n", encoding="utf-8")
    (skill_dir / "lint.py").write_text("print('lint')\n", encoding="utf-8")

    result = run_myteam(initialized_project, "get", "skill", "python")

    assert result.exit_code == 0
    assert "SKILL LOAD MARKER" in result.stdout
    assert "Use Python." in result.stdout
    assert "name: Python" not in result.stdout
    assert "python/testing" in result.stdout
    assert "lint.py" in result.stdout


def test_uppercase_definition_files_are_accepted(run_myteam, initialized_project: Path):
    role_dir = initialized_project / ".myteam" / "developer"
    role_dir.mkdir()
    (role_dir / "ROLE.md").write_text("Uppercase role\n", encoding="utf-8")
    (role_dir / "load.py").write_text(
        "#!/usr/bin/env python3\n"
        "from __future__ import annotations\n\n"
        "from pathlib import Path\n\n"
        "from myteam.utils import print_instructions, get_myteam_root, explain_skills, explain_roles, explain_tools, list_skills, list_roles, list_tools, print_directory_tree\n\n"
        "def main() -> int:\n"
        "    base = Path(__file__).resolve().parent\n"
        "    print('UPPERCASE ROLE LOAD MARKER')\n"
        "    print_instructions(base)\n"
        "    myteam = get_myteam_root(base)\n"
        "    print_directory_tree(myteam.parent)\n"
        "    explain_roles()\n"
        "    list_roles(base, myteam, [])\n"
        "    explain_skills()\n"
        "    list_skills(base, myteam, [])\n"
        "    explain_tools()\n"
        "    list_tools(base, myteam, [])\n"
        "    return 0\n\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )

    skill_dir = initialized_project / ".myteam" / "python"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("Uppercase skill\n", encoding="utf-8")
    (skill_dir / "load.py").write_text(
        "#!/usr/bin/env python3\nfrom __future__ import annotations\n\n"
        "from pathlib import Path\n\n"
        "from myteam.utils import print_instructions, get_myteam_root, list_roles, list_skills, list_tools\n\n"
        "def main() -> int:\n"
        "    base = Path(__file__).resolve().parent\n"
        "    print('UPPERCASE SKILL LOAD MARKER')\n"
        "    print_instructions(base)\n"
        "    myteam = get_myteam_root(base)\n"
        "    list_roles(base, myteam, [])\n"
        "    list_skills(base, myteam, [])\n"
        "    list_tools(base, myteam, [])\n"
        "    return 0\n\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )

    role_result = run_myteam(initialized_project, "get", "role", "developer")
    skill_result = run_myteam(initialized_project, "get", "skill", "python")

    assert role_result.exit_code == 0
    assert "UPPERCASE ROLE LOAD MARKER" in role_result.stdout
    assert "Uppercase role" in role_result.stdout
    assert skill_result.exit_code == 0
    assert "UPPERCASE SKILL LOAD MARKER" in skill_result.stdout
    assert "Uppercase skill" in skill_result.stdout


def test_missing_role_fails_clearly(run_myteam, initialized_project: Path):
    result = run_myteam(initialized_project, "get", "role", "missing")

    assert result.exit_code == 1
    assert "Not a role: missing" in result.stderr


def test_missing_skill_fails_clearly(run_myteam, initialized_project: Path):
    result = run_myteam(initialized_project, "get", "skill", "missing")

    assert result.exit_code == 1
    assert "Not a skill: missing" in result.stderr
