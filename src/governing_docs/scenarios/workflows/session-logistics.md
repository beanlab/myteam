# Agent Session CLI Logistics

`myteam start` launches or contacts the long-lived mothership TTY shell. The mothership owns the user's real terminal and forwards the interactive session to one active child process at a time.

The goal is to support nested interactive agent sessions. A child process can ask the mothership to start another child process. When this happens, the current child session is suspended, the new child becomes active, and the user's terminal is switched to the new child. When the new child reports a result, or exits cleanly with no result, the mothership terminates that child and resumes the previously suspended session.

This behaves like a small purpose-built terminal multiplexer with stack-based session handoff.

## Two roles for `myteam start`

`myteam start` has two roles.

### 1. Mothership mode

When the user runs `myteam start` directly, and no existing mothership is present, it starts the mothership.

The mothership is responsible for:

- owning the user's real TTY;
- creating and advertising a mothership socket;
- launching the initial agent CLI session, such as `codex`;
- launching nested child sessions when requested;
- forwarding terminal input/output to the active child session;
- listening on a socket for JSONL-RPC messages from children;
- suspending and resuming child sessions;
- switching the visible TTY session when the active child changes;
- maintaining a stack of suspended sessions;
- storing child results by request id;
- killing a child after it reports its result;
- treating a clean child exit without a reported result as a successful no-result completion.

### 2. Client/shim mode

When `myteam start` is invoked from inside an existing managed child session, it should not start a second mothership. Instead, it should behave as a blocking client/shim for the existing mothership.

For example, from inside the first agent session:

```text
terminal -> mothership `myteam start` -> codex1
                                           |
                                           v
                                      `myteam start` client/shim
```

The inner `myteam start` connects to the existing mothership socket, requests a nested workflow, waits until that workflow completes, prints the child's JSON result to stdout, and exits with an appropriate status code.

The presence of an existing mothership can be detected through environment variables injected into managed child sessions, for example:

```text
MYTEAM_MOTHERSHIP_SOCKET=/path/to/socket
MYTEAM_SESSION_ID=<current-session-id>
```

So the runtime shape is not truly this:

```text
terminal -> myteam start -> codex1 -> myteam start -> codex2
```

Instead it is this:

```text
terminal
    |
    v
mothership `myteam start`
    |
    v
codex1 PTY session
    |
    v
inner `myteam start` client/shim
    |
    | JSONL-RPC over mothership socket
    v
mothership launches codex2 PTY session
```

Then the user-facing terminal is switched to:

```text
terminal -> mothership -> codex2 PTY session
```

When `codex2` finishes, the terminal is switched back to:

```text
terminal -> mothership -> codex1 PTY session
```

From `codex1`'s perspective, its call to `myteam start` eventually completes and returns the result from `codex2`.

## Architecture

```text
user terminal
    |
    v
mothership `myteam start`
    |
    | forwards stdin/stdout/stderr to the active child session
    v
active child process
```

Children do not directly own the user's real terminal. Instead, the mothership proxies the terminal to whichever child session is currently active.

## Child communication

The mothership listens on a socket for JSONL-RPC messages from managed child sessions and `myteam start` client/shim processes running inside those sessions.

The important message types are:

- request another process start;
- poll for a result by request id;
- report a result.

## Starting a nested process

When an active child session invokes `myteam start` to launch a child workflow, that inner `myteam start` runs in client/shim mode.

The client/shim should:

1. connect to the mothership socket;
2. send a `start_child` request containing the current parent session id and the requested workflow specification;
3. receive a request id from the mothership;
4. then wait for the result by polling the mothership by request id.

Once the mothership accepts the `start_child` request, the mothership:

1. records the currently active child session as the parent session;
2. records the request id associated with the nested child;
3. suspends the currently active child session;
4. pushes the suspended child session onto the session stack;
5. launches the requested child process in a new managed PTY session;
6. makes the new child the active session;
7. switches terminal forwarding to the new child;
8. clears the terminal.

Example:

```text
active: codex1
stack:  []

codex1 runs `myteam start child-workflow`
inner `myteam start` sends start_child request
mothership suspends codex1 session
mothership launches codex2

active: codex2
stack:  [codex1]
```

The user now sees and interacts with `codex2` instead of `codex1`.

## Polling-based result delivery

The inner `myteam start` client/shim should use polling to retrieve the nested child result.

The basic flow is:

```text
client/shim -> mothership: start_child(workflow_spec, parent_session_id)
mothership -> client/shim: accepted(request_id)

mothership suspends parent session
mothership launches child session

child session eventually reports result or exits cleanly with no result
mothership stores result or None under request_id
mothership terminates child session
mothership resumes parent session

client/shim -> mothership: poll_result(request_id)
mothership -> client/shim: result(request_id, status, payload)

client/shim prints JSON result to stdout (`null` for no result)
client/shim exits
```

The client/shim may be suspended as part of the parent session after it receives the request id. That is expected. When the parent session is resumed, the client/shim continues polling, receives the stored result or no-result value, prints it, and exits. The parent agent then observes its `myteam start` command completing normally.

The mothership should store results durably enough that a resumed client/shim can retrieve them by request id. Results should remain available until they are acknowledged or otherwise garbage-collected.

## Result format

When a nested child workflow completes, the inner `myteam start` client/shim prints the child's result as JSON to stdout. If the child completed with no result, it prints JSON `null`.

For small and medium results, the JSON payload can contain the result directly:

```json
{
  "status": "ok",
  "result": {
    "summary": "child workflow completed",
    "value": 123
  }
}
```

For large results or artifacts, the child workflow can write data to a file and return a JSON payload containing the path:

```json
{
  "status": "ok",
  "result": {
    "path": "/path/to/generated-result.json"
  }
}
```

The `myteam start` client/shim should use its exit code to indicate high-level success or failure:

- `0` for successful child completion, including no-result completion;
- non-zero for failed, cancelled, or unavailable results.

Human-oriented diagnostics should go to stderr. Machine-readable child results should go to stdout as JSON. No-result completion is represented as JSON `null`, not `{}`.

## Reporting a result

When the active child reports a result, the mothership:

1. records the reported result under the request id that launched the active child;
2. kills or otherwise terminates the reporting child;
3. checks the suspended session stack;
4. if a suspended process exists, pops the top process from the stack;
5. resumes that process;
6. makes it the active session;
7. switches terminal forwarding back to it;
8. clears the terminal.

When the active child exits cleanly without reporting a result, such as via `/quit`, the mothership follows the same suspend/resume behavior but stores a successful no-result completion. The output for that request is `None` and is serialized to CLI callers as JSON `null`. Non-zero exits remain failures.

Example:

```text
active: codex2
stack:  [codex1]

codex2 reports result, or exits cleanly with no result
mothership stores result or None for request id
mothership terminates codex2
mothership resumes codex1

active: codex1
stack:  []
```

After `codex1` resumes, the inner `myteam start` client/shim polls for the request id, receives the stored result or no-result value, prints the JSON result to stdout (`null` for no result), and exits. From `codex1`'s perspective, its command has completed with the child workflow result.

## Nested session model

The session stack allows arbitrary nesting:

```text
active: A
stack:  []

A starts B
active: B
stack:  [A]

B starts C
active: C
stack:  [A, B]

C reports result or exits cleanly with no result
active: B
stack:  [A]

B's inner `myteam start` prints C's result (or `null`) and exits

B reports result or exits cleanly with no result
active: A
stack:  []

A's inner `myteam start` prints B's result (or `null`) and exits
```

This means child sessions can behave like interactive subroutines. A parent can start a child, yield the terminal to that child, and later resume after the child reports its result or exits cleanly with no result.

## TTY forwarding model

The mothership should treat the user's real terminal as belonging to the outer `myteam start`, not to the child processes.

Each child session should be attached through a PTY-like forwarding layer:

```text
user terminal <-> mothership `myteam start` <-> active child PTY
```

The mothership forwards:

- user stdin to the active child;
- active child stdout/stderr back to the user terminal;
- terminal resize events to the active child;
- terminal control bytes/signals in a way that preserves normal interactive behavior.

Inactive children should not receive user input. Suspended children should not produce visible output.

## Process group and suspension behavior

When a child starts another process, the signaling child session is suspended and remembered. Suspension should apply to the managed session's relevant process group, not only to a single process, so that the agent CLI and the inner `myteam start` client/shim pause together.

For example, if `codex1` invokes `myteam start child-workflow`, the suspended process group may include:

- the `codex1` agent CLI;
- the inner `myteam start` client/shim;
- helper processes spawned by that session.

This is desirable. The client/shim sends the `start_child` request and receives a request id before the parent process group is suspended. It can then be paused while the child workflow owns the terminal. When the parent process group is resumed, the client/shim continues polling for the stored result.

The suspended session stack is LIFO:

- the most recently suspended process is the first one resumed;
- each reported result unwinds one level of nesting.

## Switching behavior

When switching from one child session to another, clearing the terminal is sufficient.

The switch does not need to preserve or replay full screen state. The active child is responsible for drawing whatever the user should see after it becomes active.

## End state

If a child reports a result, or exits cleanly with no result, and there is no suspended process on the stack, then the top-level session has completed. The mothership can then exit, return the result or no-result value to its caller, or perform whatever top-level completion behavior is appropriate for `myteam start`.
