from __future__ import annotations

from pathlib import Path
import textwrap

import pytest


def write_fake_agent_project(tmp_path: Path, script: str) -> None:
    (tmp_path / "fake_agent.py").write_text(textwrap.dedent(script), encoding="utf-8")
    (tmp_path / "fake_config.py").write_text(
        "import sys\n"
        "\n"
        "class FakeAgentConfig:\n"
        "    def build_argv(\n"
        "        self,\n"
        "        prompt_text,\n"
        "        model=None,\n"
        "        reasoning=None,\n"
        "        interactive=True,\n"
        "        session_id=None,\n"
        "        fork=False,\n"
        "        extra_args=None,\n"
        "    ):\n"
        "        return [sys.executable, 'fake_agent.py', prompt_text]\n"
        "\n"
        "    def get_exit_sequence(self):\n"
        "        return b'exit\\n'\n"
        "\n"
        "    def locate_session_data(self, nonce, context):\n"
        "        return context.launch_cwd / 'native-session.txt'\n"
        "\n"
        "    def get_session_id(self, session_data):\n"
        "        return 'native-session'\n"
        "\n"
        "    def get_usage_info(self, session_data):\n"
        "        return None\n",
        encoding="utf-8",
    )
    (tmp_path / ".myteam.yaml").write_text(
        "agents:\n  fake-agent: fake_config.py::FakeAgentConfig\n",
        encoding="utf-8",
    )


def test_start_python_workflow_prints_only_reported_result_text(run_myteam, tmp_path: Path) -> None:
    workflow = tmp_path / "workflow.py"
    workflow.write_text(
        "import sys\n"
        "from myteam.workflows import report_workflow_result\n"
        "print('live stdout')\n"
        "print('live stderr', file=sys.stderr)\n"
        "report_workflow_result('first')\n"
        "report_workflow_result(None)\n"
        "report_workflow_result('second')\n",
        encoding="utf-8",
    )

    result = run_myteam(tmp_path, "start", "workflow.py")

    assert result.exit_code == 0
    assert result.stdout == "first\nsecond\n"
    assert result.stderr == ""


def test_start_python_workflow_propagates_exit_code_and_passes_args(run_myteam, tmp_path: Path) -> None:
    workflow = tmp_path / "workflow.py"
    workflow.write_text(
        "import sys\n"
        "from myteam.workflows import report_workflow_result\n"
        "report_workflow_result('args=' + ','.join(sys.argv[1:]))\n"
        "sys.exit(5)\n",
        encoding="utf-8",
    )

    result = run_myteam(tmp_path, "start", "workflow.py", "alpha", "beta")

    assert result.exit_code == 5
    assert result.stdout == "args=alpha,beta\n"


def test_start_python_workflow_with_no_result_prints_nothing(run_myteam, tmp_path: Path) -> None:
    workflow = tmp_path / "workflow.py"
    workflow.write_text("print('live only')\n", encoding="utf-8")

    result = run_myteam(tmp_path, "start", "workflow.py")

    assert result.exit_code == 0
    assert result.stdout == ""
    assert result.stderr == ""


@pytest.mark.parametrize(
    ("filename", "metadata", "field", "actual", "expected"),
    [
        ("invalid.py", "usage: 7", "usage", "int", "string"),
        ("invalid.md", "input: []", "input", "list", "mapping"),
        ("invalid.md", "output: value", "output", "str", "mapping"),
    ],
)
def test_start_rejects_invalid_workflow_metadata_before_launch(
    run_myteam,
    tmp_path: Path,
    filename: str,
    metadata: str,
    field: str,
    actual: str,
    expected: str,
) -> None:
    marker = tmp_path / "launched.txt"
    if filename.endswith(".py"):
        source = (
            f'\"\"\"\ntype: workflow\ndescription: invalid\n{metadata}\n\"\"\"\n'
            "from pathlib import Path\n"
            "Path('launched.txt').write_text('launched', encoding='utf-8')\n"
        )
    else:
        write_fake_agent_project(
            tmp_path,
            """
            import sys
            from pathlib import Path
            from myteam.workflows.results import report_result
            Path('native-session.txt').write_text('native-session', encoding='utf-8')
            report_result({'unexpected_launch': True})
            assert sys.stdin.readline() == 'exit\\n'
            """,
        )
        source = (
            f"---\ntype: workflow\ndescription: invalid\nagent: fake-agent\n{metadata}\n---\n"
            "{{ shell(\"python -c \\\"from pathlib import Path; "
            "Path('launched.txt').write_text('launched')\\\"\") }}\n"
        )
    (tmp_path / filename).write_text(source, encoding="utf-8")

    result = run_myteam(tmp_path, "start", filename)

    assert result.exit_code != 0
    assert result.stdout == ""
    assert filename in result.stderr
    assert field in result.stderr
    assert actual.lower() in result.stderr.lower()
    assert expected.lower() in result.stderr.lower()
    assert not marker.exists()


def test_start_accepts_yaml_native_values_inside_markdown_input_mapping(
    run_myteam, tmp_path: Path
) -> None:
    write_fake_agent_project(
        tmp_path,
        """
        import sys
        from pathlib import Path
        from myteam.workflows.results import report_result
        Path('native-session.txt').write_text('native-session', encoding='utf-8')
        report_result({'launched': True})
        assert sys.stdin.readline() == 'exit\\n'
        """,
    )
    (tmp_path / "workflow.md").write_text(
        "---\n"
        "type: workflow\n"
        "description: YAML-native schema\n"
        "agent: fake-agent\n"
        "input:\n"
        "  1: numeric key\n"
        "  when: 2025-01-02\n"
        "  estimate: .nan\n"
        "---\nbody\n",
        encoding="utf-8",
    )

    result = run_myteam(tmp_path, "start", "workflow.md")

    assert result.exit_code == 0
    assert result.stdout == '{"launched": true}\n'
    assert result.stderr == ""


def test_start_markdown_workflow_presents_yaml_native_output_schema_as_yaml(
    run_myteam, tmp_path: Path
) -> None:
    write_fake_agent_project(
        tmp_path,
        """
        import sys
        from pathlib import Path
        from myteam.workflows.results import report_result

        prompt = sys.argv[1]
        Path('native-session.txt').write_text('native-session', encoding='utf-8')
        report_result({
            'launched': True,
            'numeric_key_preserved': '\\n1: numeric result field' in prompt,
            'date_preserved': 'completed_at: 2025-01-02' in prompt,
            'yaml_fence': '```yaml' in prompt,
            'json_reporting': 'valid JSON' in prompt,
        })
        assert sys.stdin.readline() == 'exit\\n'
        """,
    )
    (tmp_path / "workflow.md").write_text(
        "---\n"
        "type: workflow\n"
        "description: YAML-native output schema\n"
        "agent: fake-agent\n"
        "output:\n"
        "  1: numeric result field\n"
        "  completed_at: 2025-01-02\n"
        "---\nbody\n",
        encoding="utf-8",
    )

    result = run_myteam(tmp_path, "start", "workflow.md")

    assert result.exit_code == 0
    assert result.stderr == ""
    assert result.stdout == (
        '{"launched": true, "numeric_key_preserved": true, '
        '"date_preserved": true, "yaml_fence": true, "json_reporting": true}\n'
    )


def test_start_markdown_workflow_reports_agent_output_as_json_text(run_myteam, tmp_path: Path) -> None:
    write_fake_agent_project(
        tmp_path,
        """
        import sys
        from pathlib import Path
        from myteam.workflows.results import report_result

        prompt = sys.argv[1]
        Path('native-session.txt').write_text('native-session', encoding='utf-8')
        report_result({'summary': 'ok', 'saw_rendered_prompt': 'Review release.' in prompt})
        assert sys.stdin.readline() == 'exit\\n'
        """,
    )
    workflow = tmp_path / "review.md"
    workflow.write_text(
        "---\n"
        "type: workflow\n"
        "description: review a topic\n"
        "agent: fake-agent\n"
        "input:\n"
        "  topic: topic to review\n"
        "output:\n"
        "  summary: short summary\n"
        "---\n"
        "Review {{ topic }}.\n",
        encoding="utf-8",
    )

    result = run_myteam(tmp_path, "start", "review.md", "--input", '{"topic": "release"}')

    assert result.exit_code == 0
    assert result.stdout == '{"summary": "ok", "saw_rendered_prompt": true}\n'
    assert result.stderr == ""


def test_start_markdown_workflow_renders_document_relative_jinja_helpers(run_myteam, tmp_path: Path) -> None:
    write_fake_agent_project(
        tmp_path,
        """
        import sys
        from myteam.workflows.results import report_result

        prompt = sys.argv[1]
        report_result({'prompt_has_fragment': '## Workflow fragment' in prompt})
        assert sys.stdin.readline() == 'exit\\n'
        """,
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "fragment.txt").write_text("# Workflow fragment", encoding="utf-8")
    workflow = docs / "review.md"
    workflow.write_text(
        "---\n"
        "type: workflow\n"
        "description: review a topic\n"
        "agent: fake-agent\n"
        "---\n"
        "Read {{ increase_headers(read_file('fragment.txt')) }}.\n",
        encoding="utf-8",
    )

    result = run_myteam(tmp_path, "start", "docs/review.md")

    assert result.exit_code == 0
    assert result.stdout == '{"prompt_has_fragment": true}\n'
    assert result.stderr == ""


def test_start_markdown_workflow_runs_shell_in_workflow_directory(run_myteam, tmp_path: Path) -> None:
    write_fake_agent_project(
        tmp_path,
        """
        import sys
        from myteam.workflows.results import report_result

        prompt = sys.argv[1]
        report_result({'prompt_has_shell_output': 'workflow shell output' in prompt})
        assert sys.stdin.readline() == 'exit\\n'
        """,
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "shell-marker.txt").write_text("workflow shell output", encoding="utf-8")
    workflow = docs / "review.md"
    workflow.write_text(
        "---\n"
        "type: workflow\n"
        "description: review a topic\n"
        "agent: fake-agent\n"
        "---\n"
        "Read {{ shell('cat shell-marker.txt') }}.\n",
        encoding="utf-8",
    )

    result = run_myteam(tmp_path, "start", "docs/review.md")

    assert result.exit_code == 0
    assert result.stdout == '{"prompt_has_shell_output": true}\n'
    assert result.stderr == ""
