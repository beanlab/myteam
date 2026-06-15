# `myteam.workflows.execution`

Workflow-level supervision and nested workflow runtime.

## Shape

- `myteam.workflows.commands` is the public command/API surface used by `myteam start` and `run_agent(...)`.
- `myteam.workflows.agent_session` owns standalone `run_agent(...)` child-agent execution.
- `myteam.workflows.agent_result_channel` owns the per-`run_agent` result socket used by `myteam result`.
- `myteam.workflows.results` owns `SessionResult`, `UsageInfo`, and `myteam result` reporting.
- `myteam.workflows.workflow_result` owns explicit workflow result text reporting for `myteam start`.
- `mothership.py` coordinates the workflow supervisor Unix-socket RPC server, workflow requests, workflow result storage, and nested `myteam start` polling.
- `pty_process.py`, `terminal.py`, and `recording.py` contain PTY/terminal helpers that will be reused when workflow supervision is moved to the final PTY/process-group model.
- `protocol.py` contains JSON RPC client/helpers and shared workflow-supervisor environment variable names.

A workflow invocation may call `run_agent(...)` many times. Those agent sessions are managed by `run_agent` itself, not by the workflow supervisor. Nested `myteam start` calls use the active supervisor socket, request a child workflow, poll for that workflow process result, then print the child workflow's explicit result text and exit with the child workflow exit code. Workflow stdout/stderr are live display/logging streams; they are not returned as the `myteam start` result.

The workflow supervisor control socket supports:

- `start_workflow`
- `poll_result`
- `ack_result`
- `workflow_result`

The workflow supervisor socket is separate from the per-agent result socket owned by each `run_agent(...)` call.
