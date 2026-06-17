# Starting Workflows

`myteam start` launches or contacts the long-lived supervisor TTY shell. The supervisor owns the user's real terminal and forwards the interactive session to one active child workflow process tree at a time.

The goal is to support nested interactive agent sessions inside of workflows. A child workflow process can ask the supervisor to start another child process. When this happens, the current child process is suspended, the new child becomes active, and the user's terminal is switched to the new child. When the new child exits, the supervisor resumes the previously suspended process.

This behaves like a small purpose-built terminal multiplexer with stack-based process handoff.

## Workflow result text

`myteam start` returns text for a human or AI agent caller. Workflows return this text explicitly by calling `report_workflow_result(...)`. Ordinary `print(...)` output is live display/logging; it is not the returned `myteam start` result.

```python
from myteam.workflows import report_workflow_result

report_workflow_result("final text returned by myteam start")
```

`report_workflow_result(...)` appends a newline by default (`end="\n"`), matching Python's `print(...)`. Pass `end=""` to report text exactly as supplied.

`report_workflow_result(...)` may be called multiple times. The supervisor concatenates non-`None` text fragments in call order. Calling `report_workflow_result(None)` appends no text. If a workflow reports no text, `myteam start` prints nothing for that workflow result.

Workflow stdout/stderr are live display/logging streams. They are not the returned result of `myteam start`. The supervisor may record display transcripts for debugging, but PTY transcripts are not replayed as result text.

## `myteam start` play-by-play

- User calls `myteam start workflow.py`
    - no supervisor process is running yet, so this becomes the supervisor
        - it then launches another `myteam start workflow.py` process
    - this second process connects to the supervisor and requests that workflow.py start
    - supervisor launches `python workflow.py` subprocess
- workflow.py calls `run_agent(agent1)`
    - `run_agent` starts agent1 session
- agent1 session calls `myteam start other_workflow.py`
    - `myteam start` connects to existing supervisor and requests `other_workflow.py` start
    - supervisor suspends workflow.py process tree (including agent1 session and
      `myteam start other_workflow.py` command)
    - supervisor launches the `python other_workflow.py` subprocess
- other_workflow.py calls `run_agent(agent2)`
    - `run_agent` launches agent2 session
- agent2 calls `myteam result`
    - `myteam result` connects to other_workflow.py `run_agent` and sends the agent result
    - other_workflow.py `run_agent` closes agent2 session and returns `SessionResult` to workflow code
- other_workflow.py chooses what text to return to its caller
    - for example, it may call `report_workflow_result(...)` with text derived from `SessionResult.output`
- other_workflow.py does additional work and eventually concludes
    - supervisor notes conclusion and stores the reported workflow result text
- supervisor resumes workflow.py process tree including agent1 session and
  `myteam start` command and routes other_workflow.py reported result text to the output of `myteam start other_workflow.py`
    - agent1 sees only the child workflow's reported result text, not the child workflow's PTY/TUI transcript
- agent1 calls `myteam result` and concludes
    - `myteam result` connects to workflow.py `run_agent` and reports the agent result
    - workflow.py `run_agent` closes agent1 session and returns `SessionResult` to workflow code
- workflow.py chooses what text to return by calling `report_workflow_result(...)`
- workflow.py concludes
- supervisor has no more managed processes and exits

So the runtime shape is not truly this:

```text
terminal -> myteam start -> workflow.py -> agent1 -> myteam start -> other_workflow.py -> agent2
```

Instead, it is this:

```text
terminal -> myteam start workflow.py -> supervisor
                                     -> myteam start workflow.py
                        (supervisor) -> workflow.py -> agent1 -> myteam start other_workflow.py
                        (supervisor) -> (suspends) workflow.py ...
                        (supervisor) -> other_workflow.py -> agent2
                        (supervisor) -> (resumes) workflow.py ...
```

From `agent1`'s perspective, its call to `myteam start` eventually completes and prints the reported result text from `other_workflow.py`.

## Design

`myteam start` connects to the supervisor process via socket. This socket is shared by all workflow processes and identified by environment variable.
`myteam start` requests that a workflow process be started. This is a different socket than that used by `run_agent` for agent result reporting, but workflows also use the supervisor socket to report workflow result text.

The supervisor has only one process `start`ed at a time. When a new process is requested via a nested
`myteam start`, it suspends the active process tree and starts the new one. When the new one finishes, it resumes the prior process tree recursively. The explicit result text reported by the
`start`ed process is returned as the output of `myteam start`.

So, if the supervisor is not already running,
`myteam start` becomes the supervisor and the requests (of itself) to start the first process. All other calls to
`myteam start` simply connect to the supervisor.

## Supervisor

The supervisor is responsible for:

- owning the user's real TTY;
- creating and advertising a supervisor socket;
- launching the initial workflow process;
- launching nested workflow processes when requested;
- forwarding terminal input/output to the active child workflow;
- listening on a socket for nested workflow requests and workflow result reports;
- suspending and resuming child workflows;
- switching the visible TTY session when the active child changes;
- maintaining a stack of suspended workflows;
- storing reported workflow result text by request id;

## Nested mode

When
`myteam start` is invoked from inside an existing managed child session, it should not start a second supervisor. Instead, it communicates back to the supervisor to request a new workflow be run.

The inner
`myteam start` connects to the existing supervisor socket, requests a nested workflow, waits until that workflow completes, prints the workflow's reported result text if any, and exits with an appropriate status code.

The presence of an existing supervisor can be detected through environment variables injected into managed child workflows, for example:

```text
MYTEAM_SUPERVISOR_SOCKET=/path/to/socket
MYTEAM_WORKFLOW_INVOCATION_ID=<current-workflow-process-id>
```

## TTY Architecture

```text
user terminal
    |
    v
supervisor `myteam start`
    |
    | forwards stdin/stdout/stderr to the active child process
    v
active child process
```

Children do not directly own the user's real terminal. Instead, the supervisor proxies the terminal to whichever child workflow is currently active.

PTY display is distinct from workflow result text. Active workflow display is shown live; it is not replayed as `myteam start` output after completion.

## Polling-based result delivery

The inner `myteam start` client/shim should use polling to retrieve the nested child result text.

The basic flow is:

```text
client/shim -> supervisor: start_child(workflow_spec, parent_session_id)
supervisor -> client/shim: accepted(workflow ID)

supervisor suspends parent process
supervisor launches child process

child workflow process reports result text zero or more times
child workflow process tree eventually exits
supervisor stores concatenated result text under workflow ID
supervisor resumes parent process

client/shim -> supervisor: poll_output(workflow ID)
supervisor -> client/shim: output(workflow ID, status, payload)

client/shim prints reported result text if any
client/shim exits
```

The client/shim may be suspended as part of the parent session after it receives the workflow ID. That is expected. When the parent session is resumed, the client/shim continues polling, receives the stored result text, prints it, and exits. The parent agent then observes its
`myteam start` command completing normally.

The supervisor should store results durably enough that a resumed client/shim can retrieve them by workflow ID. Results should remain available until they are acknowledged or otherwise garbage-collected.

## Result format

When a nested child workflow completes, the inner
`myteam start` client/shim prints the child's reported workflow result text. It does not print the child's PTY display transcript, agent subsession transcript, or live logging output.

The JSONL-RPC payload will contain the result text directly:

```json
{
  "exit-code": 0,
  "result_text": "hello world\n"
}
```

The `myteam start` client/shim should use its exit code to indicate high-level success or failure:

- `0` for successful child completion;
- non-zero for failed, cancelled, or unavailable results.

## TTY forwarding model

The supervisor should treat the user's real terminal as belonging to the outer
`myteam start`, not to the child processes.

Each child process should be attached through a PTY-like forwarding layer:

```text
user terminal <-> supervisor `myteam start` <-> active child workflow PTY
```

The supervisor forwards:

- user stdin to the active child;
- active child stdout/stderr back to the user terminal as live display/logging;
- terminal resize events to the active child;
- terminal control bytes/signals in a way that preserves normal interactive behavior.

Inactive workflows should not receive user input. Suspended workflows should not produce visible output.

### Switching behavior

When switching from one child PTY session to another, clearing the terminal is sufficient.

The switch does not need to preserve or replay full screen state. The active child is responsible for drawing whatever the user should see after it becomes active.

The supervisor should flush pending real-terminal input around session switches and final terminal restore so terminal-query response bytes are not delivered to the wrong process or left at the shell prompt.

## Process group and suspension behavior

When a child starts another process, the signaling child process is suspended and remembered. Suspension should apply to the managed session's relevant process group, not only to a single process, so that the workflow, agent CLI, and the inner
`myteam start` client/shim pause together.

For example, if `workflow.py` calls `agent1` which invokes
`myteam start child-workflow`, the suspended process group should include:

- `workflow.py`
- the `agent1` agent CLI;
- the inner `myteam start` client/shim

This is desirable. The client/shim sends the
`start_child` request and receives a workflow id before the parent process group is suspended. It can then be paused while the child workflow owns the terminal. When the parent process group is resumed, the client/shim continues polling for the stored result.

The suspended session stack is LIFO:

- the most recently suspended process is the first one resumed;
- each workflow exit unwinds one level of nesting.
