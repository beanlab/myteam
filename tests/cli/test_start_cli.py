from __future__ import annotations

from pathlib import Path
import textwrap


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
        "report_workflow_result('first\\n')\n"
        "report_workflow_result(None)\n"
        "report_workflow_result('second\\n')\n",
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
        "report_workflow_result('args=' + ','.join(sys.argv[1:]) + '\\n')\n"
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
