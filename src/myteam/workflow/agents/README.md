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

def build_argv(
    prompt_text: str,
    interactive: bool = True,
    resume_session_id: str | None = None,
    fork_session_id: str | None = None,
    extra_args: list[str] | None = None,
) -> list[str]:
    ...
```

Instead of `EXIT_COMMAND` as a string that uses `encode_input` from `agent_utils.py`, you
may encode bytes directly with `EXIT_SEQUENCE`. When both `EXIT_SEQUENCE` and
`EXIT_COMMAND` are present, `EXIT_SEQUENCE` takes precedence.

### `EXEC`

`EXEC` is the command name used to launch the agent CLI. It must be a string.

### `build_argv(prompt_text, interactive=True, resume_session_id=None, fork_session_id=None, extra_args=None)`

`build_argv` returns the argv list used to start the agent process.

Use `resume_session_id` to resume an existing session and `fork_session_id` to
fork an existing session into a new one. `extra_args` contains optional
workflow-authored argv items that the agent config places wherever that CLI
expects additional flags. Different CLIs use different syntax:

```python
def build_argv(
    prompt_text: str,
    interactive: bool = True,
    resume_session_id: str | None = None,
    fork_session_id: str | None = None,
    extra_args: list[str] | None = None,
) -> list[str]:
    extras = extra_args or []
    if resume_session_id is not None:
        return ["codex", "resume", resume_session_id, *extras, prompt_text]
    if fork_session_id is not None:
        return ["codex", "fork", fork_session_id, *extras, prompt_text]
    if not interactive:
        return ["codex", "exec", *extras, prompt_text]
    return ["codex", *extras, prompt_text]
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
- `context.project_root`: resolved project root
- `context.launch_cwd`: resolved working directory used to launch the agent

A typical implementation searches the agent CLI's session files newest-first,
looks for the nonce, extracts the session id from the matching filename, and
raises `LookupError` if no match can be found (See example below).

Session discovery should be conservative:

- search newest files first
- ignore unreadable files
- match the nonce inside the file contents, not just by timestamp
- raise an exception when discovery fails instead of guessing

## Example

See [codex.py](codex.py) or [pi.py](pi.py) for examples

## Recipe: making an agent alias for a specific configuration

Let's say you want to create an agent alias that launches codex with specific
command-line flags included. For example, let's create an agent named
`codex_mini` that uses `--model gpt-5.4-mini`. Create a file in
`.myteam/.configs/`. If you named it `codex_mini.py`, you would run it by
passing `agent="codex_mini"` into `run_agent`.

```python
from __future__ import annotations

from myteam.workflow.agents.codex import EXEC, EXIT_COMMAND, get_session_id
from myteam.workflow.agents.codex import build_argv as build_codex_argv


def build_argv(
    prompt_text: str,
    interactive: bool = True,
    resume_session_id: str | None = None,
    fork_session_id: str | None = None,
    extra_args: list[str] | None = None,
) -> list[str]:
    argv = build_codex_argv(
        prompt_text,
        interactive,
        resume_session_id,
        fork_session_id,
        extra_args=extra_args,
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
