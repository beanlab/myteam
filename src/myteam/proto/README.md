# `myteam.proto`

Minimum prototype for workflow-level supervision and nested interactive agent sessions.

## Shape

- `commands.py` is the command-facing API used by `myteam start`, `run_agent`, and `myteam result`.
- `mothership.py` coordinates the Unix-socket RPC server, workflow requests, agent-session requests, session stack, result storage, and active-session switching.
- `pty_process.py` launches and manages one child agent process attached to one PTY.
- `terminal.py` owns real-terminal raw mode, resize handling, clearing, input, and output.
- `recording.py` captures simple per-session transcripts.
- `protocol.py` contains the tiny JSON RPC client/helpers and shared environment variable names.

## Core behavior

A `myteam` supervisor/mothership owns one workflow invocation. A workflow invocation may call `run_agent` many times. Those agent sessions all use the same supervisor.

### Top-level `myteam start`

When `myteam start <workflow>` is invoked and `MYTEAM_MOTHERSHIP_SOCKET` is absent:

1. `myteam start` creates a mothership in-process.
2. The mothership starts the workflow as an ordinary subprocess with supervisor environment variables.
3. The workflow subprocess calls `run_agent(...)` as needed.
4. Each `run_agent(...)` call sends `start_agent_session` to the mothership.
5. The mothership launches the requested agent CLI session under a managed PTY.
6. The agent session reports completion with `myteam result`.
7. The workflow receives the `SessionResult` and may call `run_agent(...)` again.
8. When the workflow subprocess exits, the top-level `myteam start` returns the workflow result.

### Nested `myteam start`

When `myteam start <workflow>` is invoked from inside a managed agent session:

1. The inner `myteam start` detects `MYTEAM_MOTHERSHIP_SOCKET`.
2. It acts as a client/shim for the existing supervisor.
3. It sends `start_workflow` with the current parent session ID.
4. The mothership suspends the parent agent session.
5. The mothership starts the nested workflow subprocess.
6. The nested workflow may call `run_agent(...)` one or more times.
7. When the nested workflow completes, the mothership resumes the suspended parent session.
8. The inner `myteam start` shim prints the nested workflow result as JSON and exits.

### `run_agent`

`run_agent(...)` requires an active supervisor. It does not create a mothership by itself.

When called from a workflow subprocess:

1. `run_agent(...)` sends `start_agent_session` to the supervisor.
2. The supervisor launches an agent CLI session under a PTY.
3. The agent receives supervisor/session environment variables.
4. The agent eventually calls `myteam result`.
5. The supervisor records the output, transcript, usage placeholder, session ID, and nonce.
6. `run_agent(...)` receives and returns a `SessionResult`.

Calling plain `run_agent(...)` outside `myteam start` is an error in this prototype.

## Managed child environment

Managed child agent sessions receive conceptually:

```text
MYTEAM_MOTHERSHIP_SOCKET=<socket path>
MYTEAM_REQUEST_ID=<request id>
MYTEAM_SESSION_ID=<managed session id>
MYTEAM_SESSION_NONCE=<nonce>
MYTEAM_AGENT_PROMPT=<prompt text>
MYTEAM_AGENT_INPUT_JSON=<input json, if provided>
MYTEAM_AGENT_OUTPUT_JSON=<output schema json, if provided>
```

Workflow subprocesses receive conceptually:

```text
MYTEAM_MOTHERSHIP_SOCKET=<socket path>
MYTEAM_WORKFLOW_INVOCATION_ID=<workflow request id>
MYTEAM_WORKFLOW_INPUT_JSON=<input json, if provided>
```

## RPC kinds

The prototype control socket currently supports:

- `start_workflow`
- `start_agent_session`
- `report_result`
- `poll_result`
- `ack_result`

The socket is the supervisor control socket. It is not a one-off result socket for a single `run_agent` call.

## Prototype limits

This is intentionally minimal. It demonstrates the process model and does not yet provide durability, authentication, complete job-control semantics, adapter-based agent argv generation, production-grade cleanup/recovery, or real usage extraction from agent-native session data.
