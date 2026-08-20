from __future__ import annotations

import os
from pathlib import Path
import sys
import textwrap

import pytest

from myteam.workflows import run_agent
from myteam.workflows import agent_session
from myteam.workflows.execution.protocol import ENV_SOCKET


def write_fake_agent_project(tmp_path: Path, script: str) -> None:
    (tmp_path / "fake_agent.py").write_text(textwrap.dedent(script), encoding="utf-8")
    (tmp_path / "fake_config.py").write_text(
        textwrap.dedent(
            """
            import sys

            class FakeAgentConfig:
                def build_argv(
                    self,
                    prompt_text,
                    model=None,
                    reasoning=None,
                    interactive=True,
                    session_id=None,
                    fork=False,
                    extra_args=None,
                ):
                    return [sys.executable, 'fake_agent.py', prompt_text]

                def get_exit_sequence(self):
                    return b'exit\\n'

                def locate_session_data(self, nonce, context):
                    return context.launch_cwd / 'native-session.txt'

                def get_session_id(self, session_data):
                    try:
                        return session_data.read_text(encoding='utf-8').strip()
                    except FileNotFoundError:
                        raise

                def get_usage_info(self, session_data):
                    return None
            """
        ),
        encoding="utf-8",
    )
    (tmp_path / ".myteam.yaml").write_text(
        "agents:\n  fake-agent: fake_config.py::FakeAgentConfig\n",
        encoding="utf-8",
    )


def test_run_agent_does_not_require_supervisor_and_returns_reported_output(tmp_path: Path, monkeypatch) -> None:
    write_fake_agent_project(
        tmp_path,
        """
        import os
        import sys
        from pathlib import Path
        from myteam.workflows.results import report_result
        from myteam.workflows.execution.protocol import ENV_AGENT_SESSION_NONCE, ENV_AGENT_SESSION_RESULT_SOCKET

        prompt = sys.argv[1]
        assert ENV_AGENT_SESSION_RESULT_SOCKET in os.environ
        Path('native-session.txt').write_text('native-123', encoding='utf-8')
        report_result({'prompt': prompt, 'nonce': os.environ[ENV_AGENT_SESSION_NONCE]})
        assert sys.stdin.readline() == 'exit\\n'
        """,
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(ENV_SOCKET, raising=False)

    result = run_agent(prompt="Hello {{ name }}", input={"name": "Ada"}, agent="fake-agent")

    assert result.exit_code == 0
    assert result.session_id == "native-123"
    assert result.output is not None
    assert result.output["nonce"]
    assert result.output["nonce"] in result.output["prompt"]
    assert "Hello Ada" in result.output["prompt"]


def test_run_agent_launches_agent_with_tty_stdio(tmp_path: Path, monkeypatch) -> None:
    write_fake_agent_project(
        tmp_path,
        """
        import sys
        from pathlib import Path
        from myteam.workflows.results import report_result

        Path('native-session.txt').write_text('native-tty', encoding='utf-8')
        report_result({
            'stdin': sys.stdin.isatty(),
            'stdout': sys.stdout.isatty(),
            'stderr': sys.stderr.isatty(),
        })
        assert sys.stdin.readline() == 'exit\\n'
        """,
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(ENV_SOCKET, raising=False)

    result = run_agent(prompt="TTY check", agent="fake-agent")

    assert result.exit_code == 0
    assert result.session_id == "native-tty"
    assert result.output == {"stdin": True, "stdout": True, "stderr": True}


def test_run_agent_returns_none_output_for_clean_exit_without_result(tmp_path: Path, monkeypatch) -> None:
    write_fake_agent_project(
        tmp_path,
        """
        from pathlib import Path
        Path('native-session.txt').write_text('native-clean-exit', encoding='utf-8')
        print('clean exit transcript')
        """,
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(ENV_SOCKET, raising=False)

    result = run_agent(prompt="No result", agent="fake-agent")

    assert result.exit_code == 0
    assert result.output is None
    assert result.session_id == "native-clean-exit"
    assert "clean exit transcript" in result.transcript


def test_run_agent_populates_nonzero_exit_code_without_result(tmp_path: Path, monkeypatch) -> None:
    write_fake_agent_project(
        tmp_path,
        """
        import sys
        sys.exit(7)
        """,
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(ENV_SOCKET, raising=False)

    result = run_agent(prompt="No result", agent="fake-agent")

    assert result.exit_code == 7
    assert result.output is None


def test_run_agent_preserves_json_string_reported_by_myteam_result(tmp_path: Path, monkeypatch) -> None:
    write_fake_agent_project(
        tmp_path,
        """
        from myteam.workflows.results import report_result
        report_result('"plain text result"')
        """,
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(ENV_SOCKET, raising=False)

    result = run_agent(prompt="Report text", agent="fake-agent")

    assert result.exit_code == 0
    assert result.output == "plain text result"


def test_run_agent_forwards_terminal_bytes_after_reported_result(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    write_fake_agent_project(
        tmp_path,
        """
        import sys
        from pathlib import Path
        from myteam.workflows.results import report_result

        Path('native-session.txt').write_text('native-clean-terminal', encoding='utf-8')
        print('visible before result', flush=True)
        report_result({'done': True})
        print('DANGLING-BYTES-AFTER-RESULT', flush=True)
        assert sys.stdin.readline() == 'exit\\n'
        """,
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(ENV_SOCKET, raising=False)
    monkeypatch.setenv("NO_COLOR", "1")

    result = run_agent(
        prompt="Report with noisy teardown",
        agent="fake-agent",
        session_name="Forced teardown",
    )
    captured = capsys.readouterr()

    assert result.exit_code == 0
    assert result.output == {"done": True}
    assert result.session_id == "native-clean-terminal"
    assert captured.err == ""
    assert captured.out.index("Session started") < captured.out.index("visible before result")
    assert captured.out.index("DANGLING-BYTES-AFTER-RESULT") < captured.out.index("Session ended")
    end_display = captured.out[captured.out.index("Session ended") :]
    assert 'name="Forced teardown"' in end_display
    assert 'session_id="native-clean-terminal"' in end_display
    assert "agent=" not in end_display
    assert "model=" not in end_display
    assert "reasoning=" not in end_display
    assert "interactive=" not in end_display
    assert "visible before result" in result.transcript
    assert "DANGLING-BYTES-AFTER-RESULT" in result.transcript
    assert "Session started" not in result.transcript
    assert "Session ended" not in result.transcript


def test_run_agent_forced_termination_drains_output_before_end_indicator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_fake_agent_project(
        tmp_path,
        """
        import os
        import signal
        import time
        from pathlib import Path
        from myteam.workflows.results import report_result

        Path('forced-agent.pid').write_text(str(os.getpid()), encoding='utf-8')
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        report_result({'done': True})
        print('remaining output before forced termination', flush=True)
        while True:
            time.sleep(1)
        """,
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(ENV_SOCKET, raising=False)
    monkeypatch.setenv("NO_COLOR", "1")

    result = run_agent(prompt="Force stop", agent="fake-agent", session_name="Forced session")
    captured = capsys.readouterr()

    assert result.output == {"done": True}
    assert "remaining output before forced termination" in result.transcript
    assert "Session ended" not in result.transcript
    assert captured.err == ""
    assert captured.out.index("remaining output before forced termination") < captured.out.index("Session ended")
    assert 'name="Forced session"' in captured.out
    forced_pid = int((tmp_path / "forced-agent.pid").read_text(encoding="utf-8"))
    with pytest.raises(ProcessLookupError):
        os.kill(forced_pid, 0)


def test_run_agent_post_launch_start_display_failure_cleans_up_and_emits_end(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_fake_agent_project(
        tmp_path,
        """
        import signal
        import time

        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        while True:
            time.sleep(1)
        """,
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(ENV_SOCKET, raising=False)
    monkeypatch.setenv("NO_COLOR", "1")
    original_emit = agent_session._emit_indicator
    original_launch = agent_session.ManagedPtyProcess.launch
    launched_pids: list[int] = []
    emit_count = 0

    def record_launch(**kwargs):
        session = original_launch(**kwargs)
        launched_pids.append(session.process.pid)
        return session

    def fail_after_start_display(*args) -> None:
        nonlocal emit_count
        emit_count += 1
        original_emit(*args)
        if emit_count == 1:
            raise OSError("display failed")

    monkeypatch.setattr(agent_session.ManagedPtyProcess, "launch", record_launch)
    monkeypatch.setattr(agent_session, "_emit_indicator", fail_after_start_display)

    with pytest.raises(OSError, match="display failed"):
        run_agent(prompt="Display failure", agent="fake-agent", session_name="Display failure")

    captured = capsys.readouterr()
    assert captured.err == ""
    assert "Session started" in captured.out
    assert "Session ended" in captured.out
    assert "session_id=" not in captured.out[captured.out.index("Session ended") :]
    assert len(launched_pids) == 1
    with pytest.raises(ProcessLookupError):
        os.kill(launched_pids[0], 0)


def test_run_agent_end_display_failure_does_not_replace_forwarding_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_fake_agent_project(
        tmp_path,
        """
        import signal
        import time

        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        while True:
            time.sleep(1)
        """,
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(ENV_SOCKET, raising=False)
    monkeypatch.delenv("NO_COLOR", raising=False)
    original_emit = agent_session._emit_indicator
    original_launch = agent_session.ManagedPtyProcess.launch
    launched_pids: list[int] = []
    emit_count = 0

    def record_launch(**kwargs):
        session = original_launch(**kwargs)
        launched_pids.append(session.process.pid)
        return session

    def fail_after_end_display(*args) -> None:
        nonlocal emit_count
        emit_count += 1
        original_emit(*args)
        if emit_count == 2:
            raise OSError("end display failed")

    def fail_forwarding(*_args, **_kwargs):
        raise RuntimeError("forwarding failed")

    monkeypatch.setattr(agent_session.ManagedPtyProcess, "launch", record_launch)
    monkeypatch.setattr(agent_session, "_emit_indicator", fail_after_end_display)
    monkeypatch.setattr(agent_session, "_forward_pty_until_complete", fail_forwarding)

    with pytest.raises(RuntimeError, match="forwarding failed"):
        run_agent(prompt="Forward failure", agent="fake-agent", session_name="Forward failure")

    captured = capsys.readouterr()
    assert captured.err == ""
    assert "Session ended" in captured.out
    end_title = captured.out.index("Session ended")
    end_display = captured.out[end_title:]
    assert captured.out.rfind("\x1b[1;34m", 0, end_title) > captured.out.rfind("\n", 0, end_title)
    assert "\x1b[1;31m" not in end_display
    assert "session_id=" not in end_display
    assert len(launched_pids) == 1
    with pytest.raises(ProcessLookupError):
        os.kill(launched_pids[0], 0)


def test_run_agent_silent_session_displays_lifecycle_on_stdout_not_in_transcript(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_fake_agent_project(tmp_path, "")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(ENV_SOCKET, raising=False)
    monkeypatch.setenv("NO_COLOR", "1")

    result = run_agent(
        prompt="Silent",
        agent="fake-agent",
        model="fake-model",
        reasoning="medium",
        interactive=False,
        session_name="Silent check",
    )
    captured = capsys.readouterr()

    assert captured.err == ""
    assert "Session started" in captured.out
    assert 'name="Silent check" agent="fake-agent"' in captured.out
    assert 'model="fake-model" reasoning="medium" interactive=false' in captured.out
    assert "Session ended" in captured.out
    assert "session_id=" not in captured.out[captured.out.index("Session ended") :]
    assert captured.out.index("Session started") < captured.out.index("Session ended")
    assert result.transcript == ""


def test_run_agent_native_output_is_unchanged_and_own_markers_are_not_recorded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_fake_agent_project(
        tmp_path,
        """
        import sys
        sys.stdout.buffer.write(b'native-\\x1b[32mbytes\\x1b[0m\\n')
        sys.stdout.flush()
        sys.exit(7)
        """,
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(ENV_SOCKET, raising=False)
    monkeypatch.setenv("NO_COLOR", "1")

    result = run_agent(prompt="Native output", agent="fake-agent", session_name="Exit seven")
    captured = capsys.readouterr()

    assert result.exit_code == 7
    assert captured.err == ""
    native_output = "native-\x1b[32mbytes\x1b[0m\r\n"
    assert native_output in captured.out
    assert captured.out.index("Session started") < captured.out.index(native_output)
    assert captured.out.index(native_output) < captured.out.index("Session ended")
    assert "\x1b[1;34m" not in captured.out
    assert "\x1b[1;31m" not in captured.out
    assert result.transcript == native_output


def test_run_agent_native_output_is_forwarded_before_the_child_can_exit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_fake_agent_project(
        tmp_path,
        """
        import time
        from pathlib import Path

        print('LIVE-NATIVE-OUTPUT', flush=True)
        deadline = time.monotonic() + 2
        while not Path('release-agent').exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        if not Path('release-agent').exists():
            raise SystemExit(9)
        """,
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(ENV_SOCKET, raising=False)
    monkeypatch.setenv("NO_COLOR", "1")

    class LiveOutput:
        def __init__(self) -> None:
            self.data = bytearray()
            self.buffer = self

        def write(self, chunk: bytes) -> None:
            self.data.extend(chunk)
            if b"LIVE-NATIVE-OUTPUT" in self.data:
                (tmp_path / "release-agent").touch()

        def flush(self) -> None:
            pass

        def fileno(self) -> int:
            raise OSError

    display = LiveOutput()
    monkeypatch.setattr(sys, "stdout", display)

    result = run_agent(prompt="Live", agent="fake-agent", session_name="Live")
    visible = display.data.decode("utf-8")

    assert result.exit_code == 0
    assert visible.index("Session started") < visible.index("LIVE-NATIVE-OUTPUT")
    assert visible.index("LIVE-NATIVE-OUTPUT") < visible.index("Session ended")
    assert result.transcript == "LIVE-NATIVE-OUTPUT\r\n"


def test_run_agent_session_name_resolution_coercion_and_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_fake_agent_project(tmp_path, "")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(ENV_SOCKET, raising=False)
    monkeypatch.setenv("NO_COLOR", "1")

    (tmp_path / ".myteam.yaml").write_text(
        "defaults:\n  session_name: Config name\n"
        "agents:\n  fake-agent: fake_config.py::FakeAgentConfig\n",
        encoding="utf-8",
    )
    from_config = run_agent(prompt="Config", agent="fake-agent")
    explicit_empty = run_agent(prompt="Empty", agent="fake-agent", session_name="")
    coerced = run_agent(prompt="Coerced", agent="fake-agent", session_name=42)  # type: ignore[arg-type]
    captured = capsys.readouterr()

    assert 'name="Config name"' in captured.out
    assert 'name=""' in captured.out
    assert 'name="42"' in captured.out
    assert from_config.transcript == explicit_empty.transcript == coerced.transcript == ""

    for invalid_name in ("two\nlines", "carriage\rreturn"):
        with pytest.raises(ValueError, match="newline"):
            run_agent(prompt="Invalid", agent="fake-agent", session_name=invalid_name)


def test_run_agent_default_name_omits_none_metadata_and_honors_no_color_presence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_fake_agent_project(tmp_path, "")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(ENV_SOCKET, raising=False)
    monkeypatch.setenv("NO_COLOR", "")

    result = run_agent(prompt="Defaults", agent="fake-agent")
    captured = capsys.readouterr()

    assert 'name="New session"' in captured.out
    assert "model=" not in captured.out
    assert "reasoning=" not in captured.out
    assert "\x1b[" not in captured.out
    assert result.transcript == ""


def test_run_agent_styled_indicator_resets_each_border_segment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_fake_agent_project(tmp_path, "")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(ENV_SOCKET, raising=False)
    monkeypatch.delenv("NO_COLOR", raising=False)

    result = run_agent(prompt="Styled", agent="fake-agent", session_name="Styled")
    captured = capsys.readouterr()

    indicator_lines = [line for line in captured.out.splitlines() if line.startswith("\x1b[1;34m")]
    assert indicator_lines
    assert "\x1b[1;31m" not in captured.out
    assert all("\x1b[0m" in line for line in indicator_lines)
    metadata_lines = [line for line in captured.out.splitlines() if "name=" in line]
    assert metadata_lines
    assert all(line.index("\x1b[0m") < line.index("name=") for line in metadata_lines)
    assert result.transcript == ""


def test_run_agent_sequential_sessions_have_isolated_ordered_indicators(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_fake_agent_project(tmp_path, "")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(ENV_SOCKET, raising=False)
    monkeypatch.setenv("NO_COLOR", "1")

    first = run_agent(prompt="First", agent="fake-agent", session_name="First session")
    second = run_agent(prompt="Second", agent="fake-agent", session_name="Second session")
    captured = capsys.readouterr()

    first_start = captured.out.index('name="First session"')
    first_end = captured.out.index("Session ended", first_start)
    second_start = captured.out.index('name="Second session"', first_end)
    second_end = captured.out.index("Session ended", second_start)
    assert first_start < first_end < second_start < second_end
    assert first.transcript == second.transcript == ""


@pytest.mark.parametrize(
    ("session_id", "fork", "expected_title", "source_field"),
    [
        (None, False, "Session started", None),
        ("prior-session", False, "Session resumed", 'session_id="prior-session"'),
        ("prior-session", True, "Session started", 'forked_from="prior-session"'),
        (None, True, "Session started", None),
    ],
)
def test_run_agent_start_title_and_source_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    session_id: str | None,
    fork: bool,
    expected_title: str,
    source_field: str | None,
) -> None:
    write_fake_agent_project(tmp_path, "")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(ENV_SOCKET, raising=False)
    monkeypatch.setenv("NO_COLOR", "1")

    run_agent(
        prompt="Start mode",
        agent="fake-agent",
        session_name="Mode",
        session_id=session_id,
        fork=fork,
    )
    start_box = capsys.readouterr().out.split("Session ended", 1)[0]

    assert expected_title in start_box
    if source_field is None:
        assert "session_id=" not in start_box
        assert "forked_from=" not in start_box
    else:
        assert source_field in start_box


def test_run_agent_nonzero_end_is_red_and_omits_failed_native_lookup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_fake_agent_project(tmp_path, "import sys\nsys.exit(7)\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(ENV_SOCKET, raising=False)
    monkeypatch.delenv("NO_COLOR", raising=False)

    result = run_agent(prompt="Fail", agent="fake-agent", session_name="Failed")
    captured = capsys.readouterr()
    end_start = captured.out.index("\x1b[1;31m")
    start_box = captured.out[:end_start]
    end_box = captured.out[end_start:]

    assert result.exit_code == 7
    assert result.session_id is None
    assert "\x1b[1;34m" in start_box
    assert "\x1b[1;31m" in end_box
    assert "session_id=" not in end_box
    assert captured.err == ""


def test_run_agent_launch_failure_has_no_lifecycle_display(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_fake_agent_project(tmp_path, "")
    (tmp_path / "fake_config.py").write_text(
        "class FakeAgentConfig:\n"
        "    def build_argv(self, *args, **kwargs): return ['definitely-missing-myteam-agent']\n"
        "    def get_exit_sequence(self): return b'exit\\n'\n"
        "    def locate_session_data(self, nonce, context): return context.launch_cwd / 'none'\n"
        "    def get_session_id(self, session_data): return None\n"
        "    def get_usage_info(self, session_data): return None\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(ENV_SOCKET, raising=False)

    with pytest.raises(FileNotFoundError):
        run_agent(prompt="Launch", agent="fake-agent", session_name="Never launched")

    captured = capsys.readouterr()
    assert "Session started" not in captured.out + captured.err
    assert "Session ended" not in captured.out + captured.err


def test_run_agent_nested_sessions_have_natural_outer_transcript_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_fake_agent_project(
        tmp_path,
        """
        import os
        from pathlib import Path
        from myteam import run_agent

        if "MYTEAM_INNER" not in os.environ:
            os.environ["MYTEAM_INNER"] = "1"
            inner = run_agent(prompt="Inner", agent="fake-agent", session_name="Inner session")
            Path('inner-transcript.txt').write_text(inner.transcript, encoding='utf-8')
        """,
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(ENV_SOCKET, raising=False)
    monkeypatch.setenv("NO_COLOR", "1")

    result = run_agent(prompt="Outer", agent="fake-agent", session_name="Outer session")
    captured = capsys.readouterr()

    outer_start = captured.out.index('name="Outer session"')
    inner_start = captured.out.index('name="Inner session"', outer_start)
    inner_end = captured.out.index("Session ended", inner_start)
    outer_end = captured.out.index("Session ended", inner_end + 1)
    assert outer_start < inner_start < inner_end < outer_end
    assert (tmp_path / "inner-transcript.txt").read_text(encoding="utf-8") == ""
    assert 'name="Inner session"' in result.transcript
    assert 'name="Outer session"' not in result.transcript
