## What These Files Own

Each `<agent>.py` file describes how to operate one terminal-backed agent:

- which executable to run and the command argv values
- what command exits the agent after `myteam workflow-result` is accepted
- how to discover the agent's session id

Terminal input encoding is shared by the runtime through
[`agent_utils.py`](agent_utils.py).

## Resolution Order

Agent configs are resolved by
[`runtime.py`](runtime.py):

1. Project-local override is prioritized:
   `.myteam/.config/<agent>.py`
2. Otherwise it falls back on packaged default:
   `myteam.workflow.agents.<agent>`

Local configs are intentionally supported so a project can use an agent CLI that
is not shipped with `myteam`, or override the default behavior of a packaged one.

## Required Module Contract

Every `<agent>.py` module must define:

```python
EXEC = "agent-executable"
EXIT_COMMAND = "/quit"

def get_session_id(nonce: str, context: AgentSessionContext) -> str:
    ...
```

It may also define:

```python
def build_argv(
    prompt_text: str,
    interactive: bool = True,
    resume_session_id: str | None = None,
    fork_session_id: str | None = None,
) -> list[str]:
    ...
```

For compatibility, existing configs may still define `EXIT_SEQUENCE` as bytes.
When both `EXIT_SEQUENCE` and `EXIT_COMMAND` are present, `EXIT_SEQUENCE` wins.

### `EXEC`

`EXEC` is the command name used to launch the agent CLI. It must be a string.

### `build_argv(prompt_text, interactive=True, resume_session_id=None, fork_session_id=None)`

`build_argv` returns the argv list used to start the agent process.

Use `resume_session_id` to resume an existing session and `fork_session_id` to
fork an existing session into a new one. Different CLIs use different syntax:

```python
def build_argv(
    prompt_text: str,
    interactive: bool = True,
    resume_session_id: str | None = None,
    fork_session_id: str | None = None,
) -> list[str]:
    if resume_session_id is not None:
        return ["codex", "resume", resume_session_id, prompt_text]
    if fork_session_id is not None:
        return ["codex", "fork", fork_session_id, prompt_text]
    if not interactive:
        return ["codex", "exec", prompt_text]
    return ["codex", prompt_text]
```

### `EXIT_COMMAND`

`EXIT_COMMAND` is the command text sent after the workflow step has submitted a
valid structured result through `myteam workflow-result`. The runtime encodes
it with the shared terminal encoding in `agent_utils.encode_input`.

For example:

```python
EXIT_COMMAND = "/quit"
```

Existing local configs can still provide already-encoded bytes:

```python
EXIT_SEQUENCE = b"exit\r"
```

### `get_session_id(nonce, context)`

`get_session_id` returns the session id for a completed step. `myteam` embeds
a nonce in the prompt, then calls this function after completion so Python
workflows can resume or fork previous sessions.

The `context` argument is an `AgentSessionContext` with explicit dependencies
for session lookup:

- `context.home`: resolved home directory for the parent process
- `context.project_root`: resolved myteam project root
- `context.launch_cwd`: resolved working directory used to launch the agent

A typical implementation searches the agent CLI's session files newest-first,
looks for the nonce, extracts the session id from the matching filename, and
raises `LookupError` if no match can be found (See example below).

Session discovery should be conservative:

- search newest files first
- ignore unreadable files
- match the nonce inside the file contents, not just by timestamp
- raise an exception when discovery fails instead of guessing

## Minimal Local Agent Example

Create a project-local config at `.myteam/.config/example.py`:

```python
from __future__ import annotations

import re
from pathlib import Path

from myteam.workflow.agents import AgentSessionContext

EXEC = "example-agent"
SESSION_ID_RE = re.compile(r"session-([0-9a-f-]{36})\.jsonl$")
EXIT_COMMAND = "/exit"


def build_argv(
    prompt_text: str,
    interactive: bool = True,
    resume_session_id: str | None = None,
    fork_session_id: str | None = None,
) -> list[str]:
    argv = [EXEC]
    if not interactive:
        argv.append("--print")
    if resume_session_id is not None:
        argv.extend(["--resume", resume_session_id])
    if fork_session_id is not None:
        argv.extend(["--fork", fork_session_id])
    argv.extend(["--prompt", prompt_text])
    return argv


def get_session_id(nonce: str, context: AgentSessionContext) -> str:
    sessions_dir = context.home / ".example-agent" / "sessions"
    for path in sorted(sessions_dir.rglob("*.jsonl"), key=_mtime, reverse=True):
        try:
            if nonce not in path.read_text(encoding="utf-8", errors="ignore"):
                continue
        except OSError:
            continue

        match = SESSION_ID_RE.search(path.name)
        if match:
            return match.group(1)

    raise LookupError(f"No Example Agent session found for nonce: {nonce}")


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0
```

## Example Alias for Codex Mini

Create a project-local config at `.myteam/.config/codex_mini.py` when you want
an adapter that behaves exactly like the built-in Codex adapter but launches
with a different argv:

```python
from __future__ import annotations

from myteam.workflow.agents.codex import EXIT_COMMAND
from myteam.workflow.agents.codex import build_argv as build_codex_argv
from myteam.workflow.agents.codex import get_session_id

EXEC = "codex"


def build_argv(
    prompt_text: str,
    interactive: bool = True,
    resume_session_id: str | None = None,
    fork_session_id: str | None = None,
) -> list[str]:
    argv = build_codex_argv(
        prompt_text,
        interactive,
        resume_session_id,
        fork_session_id,
    )
    argv[1:1] = ["--model", "gpt-5.4-mini"]
    return argv
```

A custom Python workflow can then select the alias by passing the local config
name as the `agent` value:

```python
from myteam.workflow.steps import run_agent


result = run_agent(
    agent="codex_mini",
    prompt="Summarize the release notes in three bullets.",
    output={"summary": ["bullet text"]},
)

if result.status != "completed":
    raise RuntimeError(result.error_message)

print(result.output["summary"])
```

For session-aware workflows, use `result.session_id` exactly as you would with
the built-in `codex` adapter:

```python
follow_up = run_agent(
    agent="codex_mini",
    resume_session_id=result.session_id,
    prompt="Turn the summary into a changelog entry.",
    output={"changelog": "entry text"},
)
```
