# Agent Session Management

## Overview

`myteam` provides a function named `run_agent` that launches a child agent CLI session. 

`UsageInfo` described in `usage.md`

```python
class SessionResult:
    exit_code: int
    output: dict[str, Any] | None
    usage: list[UsageInfo]
    session_id: str | None
    transcript: str
    
def run_agent(
        *,
        prompt: str,
        input: dict[str, Any] = None,
        output: dict[str, Any] | None = None,
        agent: str | None = None,
        session_name: str | None = None,
        model: str | None = None,
        reasoning: str | None = None,
        extra_args: tuple[str, ...] | None = None,
        interactive: bool | None = None,
        session_id: str | None = None,
        fork: bool | None = None,
        prompt_source_path: Path | str | None = None,
    ) -> SessionResult:
```

### Arguments

- `prompt`: the instructions passed to the agent session
- `input`: the input to the session
- `output`: a basic schema describing the required output content and format
- `agent`: the name of the agent executable to use (e.g. `codex` or `claude`)
- `session_name`: the display name used by the session lifecycle indicators
- `model`: the model used by the session (e.g. 'gpt-5.4-mini')
- `reasoning`: reasoning level for the model (e.g. 'medium')
- `interactive`: controls whether the agent session supports human interaction or runs in headless mode
- `extra_args`: additional command-line arguments to be passed to the agent session; this gives developers additional control over session customization
- `session_id`: indicates the prior agent session to resume; this value is whatever session ID the agent uses and can be obtained from a prior `SessionResult`
- `fork`: determines whether the specified session is forked or resumed. When `False`, the session is resumed in place; when `True`, it is forked and a new session is created from the history of the specified session. Fork is examined only if `session_id` is provided. 

The session name resolves from the explicit `session_name`, then `.myteam.yaml` defaults, then `New session`. An empty name is valid, non-string values are converted to text, and carriage returns or line feeds are rejected.

Before running the agent session, the prompt is rendered using `jinja2` with `**input` as inputs—i.e. the keys of the input object will all be available as variables in the jinja template. If `prompt_source_path` is provided, relative helper paths are resolved against that document.

In effect (pseudocode):

```
session_prompt = jinja.render(prompt, **input)
```

Certainly, the workflow author may choose to prepare the prompt as static text and not pass in `input`, in which case the prompt text is used as-is.

### Session Result

- `output` is whatever the agent session returned via `myteam result ...`; or `None` if the session ended some other way.
- `usage` is determined by the agent configuration and contains token and cost measures
- `session_id` is the ID of the session, as defined by the agent runtime and determined by the agent configuration
- `transcript` contains the agent session display. A session's own lifecycle indicators are excluded.

### `run_agent` output design

Design the `output` field for `run_agent` in a way to guide the agent towards completion of the desired task. Once the agent believes it has the needed information to fulfill the output schema, it will call `myteam result` and end the session. Thus, use that schema as a way of controlling what happens in the session before the session concludes.

The agent result returned by `run_agent` is not automatically returned by `myteam start`. It is returned to workflow code as `SessionResult.output`. The workflow decides what text, if any, should be returned to the `myteam start` caller by calling `report_workflow_result(...)`.

## Agent Session Play-by-play

Agent sessions are always managed by a `run_agent` invocation.

- In the workflow process, `run_agent` is called
- `run_agent` generates a session nonce and sets up a communication socket
- when running under `myteam start`, the active session appears in `myteam where` while it runs
- `run_agent` launches the agent session with env vars identifying the result socket
  - `run_agent` records session transcript while forwarding the active child session to the terminal
- The agent session either:
  - Reports a result to the workflow via `myteam result`
    - `run_agent` ends the agent session
  - Exits via `/quit` or error
    - `run_agent` uses `None` as the result
- The `run_agent` uses the agent configuration to determine the session_id and usage for the agent session
- after the session closes, it no longer appears in `myteam where`
- `run_agent` returns the associated `SessionResult` in the workflow code
- Workflow code may turn `SessionResult.output` into caller-facing text by calling `report_workflow_result(...)`

## Result Socket

`run_agent` exposes a control socket to the agent session through environment variables. This socket is used only for result reporting; it does not make a standalone `run_agent` session eligible for `myteam where`.

The exact environment variable names are implementation details, but managed child sessions need enough information to identify:

- the control socket;
- the session nonce.

Conceptually:

```text
MYTEAM_AGENT_SESSION_RESULT_SOCKET=/path/to/socket
MYTEAM_AGENT_SESSION_NONCE=<nonce>
```

## TTY and Transcript

The stdout/stderr/stdin of the active child agent session are wired through the workflow to the supervisor process and on to the user's terminal. This creates a transparent UX from the user to the active child process.

This means that `run_agent` launches the agent session in a way that it cleanly inherits stdin/out/err connections from the workflow.

Agent PTY/TUI display is live display, not workflow result text. It must not be captured and replayed as the output of `myteam start`. If a workflow wants to return information from an agent subsession to its caller, it should convert the returned `SessionResult.output` into text and call `report_workflow_result(...)`.

Every successfully launched session displays concise, bordered lifecycle indicators in the normal live display. New and forked sessions say `Session started`; resumed sessions say `Session resumed`. Resume starts include the source `session_id`, while fork starts include `forked_from`. Start metadata otherwise contains only the resolved name, agent, interactive status, and non-`None` model and reasoning values.

The end indicator appears after the agent's remaining output. It contains the name and the returned `SessionResult.session_id` when available. A known non-zero `SessionResult.exit_code` uses a red border; starts, successful ends, and ends shown when `run_agent` cannot return a session result use blue. In that case, the end indicator contains only the name. Set `NO_COLOR` (to any value, including an empty value) to disable framework styling.

The agent CLI's output passes through live without normalization and is the only content recorded in that session's `SessionResult.transcript`. A nested session's indicators may naturally appear in the outer transcript while remaining absent from the inner transcript. Lifecycle display does not affect `SessionResult.output` or workflow result text. Callers needing a clean result boundary must use `SessionResult.output` or text reported with `report_workflow_result(...)`. If a session cannot start, neither indicator may appear.

Only the active child session receives terminal input and produces visible terminal output. Suspended parent processes are paused while nested child processes are active.

## Session Nonce

When a session starts, `myteam` augments the prompt with a session identifier. This unique token is used to identify the conversation on disk so usage information and the agent-native session ID can be identified reliably.

The nonce plumbing is required for resumed/forked sessions, usage lookup, and reliable association between a managed `myteam` session and the underlying agent runtime's session data.

## Reporting Agent Session Results

When an agent session starts, `myteam` augments the provided prompt with brief instructions detailing:

- the expected output format, using the provided output schema;
- how to report the result using `myteam result`.

When the agent calls `myteam result`, that command parses the reported value as JSON, connects to the `run_agent` result socket, and sends a JSONL-RPC-style message containing the output JSON.

`myteam result` requires valid JSON. If the reported JSON is malformed, `myteam result` prints a helpful error, exits non-zero, and does not complete the managed session. The agent may fix the JSON and call `myteam result` again.

A managed agent session may also end cleanly without calling `myteam result`, for example when a human user or agent enters `/quit`. This is treated as a successful no-result completion. `run_agent` records the session metadata, transcript, and usage as usual, but the session output is `None`. This is distinct from an agent deliberately reporting an empty object (`{}`) with `myteam result '{}'`.

`run_agent` then:

1. records the reported output for the request;
2. terminates or closes the reporting child session;
3. locates the underlying agent session data using the nonce;
4. records the agent-native session ID;
5. records transcript and usage information;
6. returns the `SessionResult`.

Calling `myteam result` outside a managed session is an error.

`myteam result` reports only to the active `run_agent` invocation. It does not report to the workflow supervisor and does not directly affect `myteam start` output.

## Nested `myteam start` from a managed workflow

A managed workflow may invoke `myteam start <workflow>` to run a nested workflow.

When `myteam start` is invoked from inside an existing managed workflow, it does not create a second supervisor. Instead, it acts as a client/shim for the existing supervisor:

1. it connects to the supervisor control socket;
2. it sends a request to start the nested workflow;
3. it receives a workflow ID;
4. the supervisor suspends the current workflow;
5. the supervisor launches the nested workflow;
6. the nested workflow eventually exits;
7. the supervisor stores the reported workflow result text and resumes the parent workflow;
8. the inner `myteam start` shim retrieves the result text;
9. the shim prints the nested workflow result text, if any, and exits

From the parent workflow's perspective, `myteam start` behaves like a blocking command that eventually prints the child workflow's reported result text.

Note that the all subprocesses spawned by a workflow should inherit the `myteam` environment variables so that `myteam start` commands from those subprocesses are handled correctly. 
