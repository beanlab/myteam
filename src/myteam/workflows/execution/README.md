# `myteam.workflows.execution`

Workflow-level supervision and nested workflow runtime.

## Shape

- `myteam.workflows.commands` is the public command/API surface used by `myteam start` and `run_agent(...)`.
- `myteam.workflows.agent_session` owns standalone `run_agent(...)` child-agent execution.
- `myteam.workflows.agent_result_channel` owns the per-`run_agent` result socket used by `myteam result`.
- `myteam.workflows.results` owns `SessionResult`, `UsageInfo`, and `myteam result` reporting.
- `myteam.workflows.workflow_result` owns explicit workflow result text reporting for `myteam start`.
- `mothership.py` is the workflow supervisor facade and main PTY forwarding loop.
- `workflow_rpc.py` owns the workflow supervisor Unix-socket RPC server and RPC payload validation.
- `workflow_store.py` owns workflow request records, explicit workflow result text, poll/ack state, and final result storage.
- `workflow_stack.py` owns active/suspended workflow PTY process lifecycle, parent suspension/resume, resize, and shutdown.
- `workflow_commands.py` contains internal command messages used between the RPC server and supervisor loop.
- `live_output.py` tracks forwarded terminal output so final result text is visually separated from live workflow output.
- `pty_process.py`, `terminal.py`, and `recording.py` contain PTY/terminal helpers.
- `protocol.py` contains JSON RPC client/helpers and shared workflow-supervisor environment variable names.

A workflow invocation may call `run_agent(...)` many times. Those agent sessions are managed by `run_agent` itself, not by the workflow supervisor. Nested `myteam start` calls use the active supervisor socket, request a child workflow, poll for that workflow process result, then print the child workflow's explicit result text and exit with the child workflow exit code. Workflow stdout/stderr are live display/logging streams; they are not returned as the `myteam start` result.

The workflow supervisor control socket supports:

- `start_workflow`
- `poll_result`
- `ack_result`
- `workflow_result`

The workflow supervisor socket is separate from the per-agent result socket owned by each `run_agent(...)` call.
