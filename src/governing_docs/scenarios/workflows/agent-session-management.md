# Agent Session Management

`run_agent` starts an agent CLI session and returns a `SessionResult`.

Agent sessions are always managed by a `myteam` supervisor, also called the mothership in the CLI logistics docs. The supervisor owns the runtime for a workflow invocation: terminal forwarding, child process lifecycle, nested session handoff, result collection, transcript recording, and usage aggregation.

`run_agent` does not create an unmanaged agent process. It requests that the current supervisor start an agent session.

## Supervisor Requirement

A workflow invocation has exactly one active supervisor.

Top-level workflow invocations create this supervisor through `myteam start`:

```text
myteam start workflow.py
  -> creates supervisor for the workflow invocation
  -> runs workflow.py
  -> workflow.py calls run_agent one or more times
  -> each run_agent call uses the same supervisor
```

If a workflow calls `run_agent` multiple times, those calls do not each create their own mothership. They are separate agent-session requests handled by the same workflow-level supervisor.

For example:

```python
@workflow
def main(workflow_input):
    first = run_agent(prompt="Do the first step")
    second = run_agent(prompt="Do the second step", input=first.output)
    return second
```

The runtime shape is:

```text
myteam start workflow.py
  supervisor
    run_agent(first)  -> agent session A
    run_agent(second) -> agent session B
```

Calling `run_agent` without an active `myteam` supervisor is an error. Python workflows that use `run_agent` should be invoked with `myteam start`, not directly with `python workflow.py`.

A future explicit testing or convenience API may create a supervisor manually, but plain `run_agent(...)` is defined as requiring an existing supervisor.

## Supervisor State

The supervisor tracks state for the duration of the workflow invocation, including:

- the control socket used by managed child processes;
- the currently active agent session;
- the stack of suspended parent sessions;
- request IDs for active and completed child sessions/workflows;
- results reported by completed child sessions/workflows;
- session nonces and the associated agent session data;
- per-session transcripts;
- per-session and aggregate usage information;
- parent/child relationships between nested requests;
- lifecycle cleanup for child processes and sockets.

This state belongs to the workflow invocation as a whole, not to an individual `run_agent` call.

## Control Socket

The supervisor exposes a control socket to managed child processes through environment variables. This socket is used for both result reporting and nested workflow/session requests.

The exact environment variable names are implementation details, but managed child sessions need enough information to identify:

- the supervisor control socket;
- the current request ID;
- the current managed session ID;
- the session nonce.

Conceptually:

```text
MYTEAM_MOTHERSHIP_SOCKET=/path/to/socket
MYTEAM_REQUEST_ID=<request-id>
MYTEAM_SESSION_ID=<managed-session-id>
MYTEAM_SESSION_NONCE=<nonce>
```

The socket should be understood as the supervisor control socket, not as a one-off result socket created for a single `run_agent` call.

## TTY and Transcript

The stdout/stderr/stdin of the active child agent session are wired through the supervisor to the user's terminal. This creates a transparent UX from the user to the active child process.

Stdout/stderr/stdin are also recorded by `myteam` so that a transcript of each managed session can be returned. This transcript captures the final version of each line as it scrolls off-screen.

Only the active child session receives terminal input and produces visible terminal output. Suspended parent sessions are paused while nested child sessions are active.

## Session Nonce

When a session starts, `myteam` augments the prompt with a session identifier. This unique token is used to identify the conversation on disk so usage information and the agent-native session ID can be identified reliably.

The nonce plumbing is required for resumed/forked sessions, usage lookup, and reliable association between a managed `myteam` session and the underlying agent runtime's session data.

## Reporting Agent Session Results

When an agent session starts, `myteam` augments the provided prompt with brief instructions detailing:

- the expected output format, using the provided output schema;
- how to report the result using `myteam result`.

When the agent calls `myteam result`, that command connects to the active supervisor control socket and sends a JSONL-RPC-style message containing the output JSON and the current request ID.

The supervisor then:

1. records the reported output for the request;
2. terminates or closes the reporting child session;
3. locates the underlying agent session data using the nonce;
4. records the agent-native session ID;
5. records transcript and usage information;
6. resumes the suspended parent session, if one exists;
7. marks the request complete so the caller can receive the `SessionResult`.

Calling `myteam result` outside a managed session is an error.

## Nested `myteam start` from an Agent Session

A managed agent session may invoke `myteam start <workflow>` to run a nested workflow.

When `myteam start` is invoked from inside an existing managed session, it does not create a second supervisor. Instead, it acts as a client/shim for the existing supervisor:

1. it connects to the supervisor control socket;
2. it sends a request to start the nested workflow;
3. it receives a request ID;
4. the supervisor suspends the current agent session;
5. the supervisor launches the nested workflow/session;
6. the nested session eventually reports its result;
7. the supervisor stores the result and resumes the parent session;
8. the inner `myteam start` shim retrieves the result;
9. the shim prints the nested workflow result as JSON to stdout and exits.

From the parent agent's perspective, `myteam start` behaves like a blocking command that eventually prints the child workflow result.

The important runtime shape is:

```text
terminal
  -> top-level myteam supervisor
    -> parent agent session
      -> inner `myteam start` shim
        -> request over supervisor socket
    -> supervisor suspends parent and runs child session
    -> child reports result with `myteam result`
    -> supervisor resumes parent
    -> inner shim prints child result to parent stdout
```

## Multiple `run_agent` Calls in One Workflow

A Python workflow may call `run_agent` multiple times. Each call starts a distinct managed agent session, but all calls share the same workflow-level supervisor.

This allows the supervisor to aggregate usage and preserve a coherent runtime context across the whole workflow. It also ensures that any agent session can safely invoke nested workflows through `myteam start`, because the supervisor is already present and able to suspend/resume sessions.

The result of each `run_agent` call is a `SessionResult` for that specific agent session. The workflow may combine these results however it chooses and return a final workflow result.

## Relationship Between `run_agent`, `myteam start`, and `myteam result`

- `myteam start` creates the top-level supervisor for a workflow invocation, unless it is running inside an existing managed session.
- Nested `myteam start` calls are client/shims that delegate to the existing supervisor.
- `run_agent` submits an agent-session request to the current supervisor.
- `myteam result` reports the result of the currently active managed agent session to the supervisor.
- The supervisor is the only component that owns terminal switching, child process lifecycle, result storage, transcript collection, usage aggregation, and nested session suspend/resume behavior.

This means `run_agent` should be understood as the public API for starting managed agent sessions, not as a standalone process-spawning helper independent of the `myteam` runtime.
