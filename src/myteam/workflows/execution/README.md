# `myteam.workflows.execution`

Workflow-level supervision and nested interactive agent-session runtime.

## Shape

- `myteam.workflows.commands` is the public command/API surface used by `myteam start` and `run_agent(...)`.
- `myteam.workflows.results` owns `SessionResult`, `UsageInfo`, and `myteam result` reporting.
- `mothership.py` coordinates the Unix-socket RPC server, workflow requests, agent-session requests, session stack, result storage, and active-session switching.
- `pty_process.py` launches and manages one child agent process attached to one PTY.
- `terminal.py` owns real-terminal raw mode, resize handling, clearing, input, and output.
- `recording.py` captures simple per-session transcripts.
- `protocol.py` contains JSON RPC client/helpers and shared environment variable names.

A workflow invocation may call `run_agent(...)` many times. Those agent sessions all use the same supervisor. Nested `myteam start` calls from inside a managed agent session use the active supervisor, suspend the parent session, run the nested workflow, and resume the parent session when the nested workflow completes.

The control socket supports:

- `start_workflow`
- `start_agent_session`
- `report_result`
- `poll_result`
- `ack_result`

The socket is the supervisor control socket, not a one-off result socket for a single `run_agent(...)` call.
