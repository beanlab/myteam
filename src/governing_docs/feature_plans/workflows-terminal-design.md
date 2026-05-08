# Terminal Session Design

This folder contains the experimental terminal/PTY layers used to run interactive
agent subprocesses while preserving a transparent local terminal experience.

## Goals

The terminal stack should make an interactive child process feel like it is
running directly in the user's terminal, while still giving the workflow engine a
safe way to observe output, inject input, record diagnostics, and receive a
structured result.

The design intentionally separates these concerns:

1. **PTY transport**: launch the child process, bridge terminal IO, and expose raw
   output bytes.
2. **Terminal recording**: interpret raw terminal bytes into a rendered transcript.
3. **Result reporting**: receive the agent's final structured result through an
   out-of-band channel instead of scraping terminal output.
4. **Workflow orchestration**: combine the PTY session, recorder, and result
   channel into a step result.

Keeping these concerns separate reduces brittleness and keeps each layer easier
to reason about.

## PTY session layer

`pty_session.py` is the low-level session layer.

Its responsibilities are:

- open and close PTY file descriptors
- launch the child process attached to the PTY slave
- forward local stdin to the child when enabled
- mirror child output to local stdout when enabled
- yield raw child output bytes to callers
- accept injected input through a session-owned queue
- preserve terminal mode and window sizing behavior
- return the child process exit code when the session ends

The PTY layer should not parse prompts, classify output, track workflow results,
or understand agent-specific command submission rules.

The preferred shape is:

```python
with PtySession(argv, env=env) as session:
    for chunk in session.events():
        ...
```

The yielded value is raw `bytes`. The generator is for observation only; callers
should not be expected to send input back through `yield`.

### Queued input

Injected input should be submitted through an explicit queue API, for example:

```python
session.enqueue_input(b"/quit\x1b[C\r")
```

This lets other threads or orchestration layers request input injection without
needing to coordinate with the next generator `.send(...)` call.

A plain queue is not sufficient by itself, because the PTY event loop may be
blocked in `select.select(...)` waiting for PTY output or local stdin. The session
should pair the input queue with a wakeup pipe:

- `enqueue_input(data)` adds `data` to the queue
- `enqueue_input(data)` writes a byte to the wakeup pipe
- the PTY event loop includes the wakeup pipe read fd in `select(...)`
- when the wakeup pipe is readable, the loop drains queued input and writes it to
  the PTY master

This keeps all writes to the PTY serialized inside the PTY session loop while
still allowing asynchronous input requests.

The PTY session should write exactly the bytes it is given. It should not append
newlines, carriage returns, or agent-specific escape sequences. If a caller needs
to submit a command to a terminal UI, it must provide the complete byte sequence.
For Codex-like sessions, that may be:

```python
PTY_RIGHT_ARROW = b"\x1b[C"
exit_sequence = b"/quit" + PTY_RIGHT_ARROW + b"\r"
```

## Terminal recording layer

`terminal/recording.py` contains `TerminalRecording`, which consumes raw PTY
bytes and builds a transcript.

The recording layer is intentionally separate from the PTY session. The PTY
session only transports bytes; the recorder interprets those bytes as terminal
output.

`TerminalRecording` currently takes the simplest useful approach: it decodes each
byte chunk with UTF-8 replacement and appends the text to an in-memory buffer.
This preserves a straightforward diagnostic transcript without attempting to
render a virtual terminal screen.

Example:

```python
recording = TerminalRecording()

with PtySession(argv, env=env) as session:
    events = session.events()
    while True:
        try:
            chunk = next(events)
        except StopIteration as exc:
            exit_code = exc.value
            break

        transcript = recording.feed(chunk)
```

The transcript is useful for verbose logs, debugging failed workflow steps, and
explaining why a session did not complete as expected. It should not be used as
the primary structured result channel.

## Result reporting layer

Terminal output is a poor control channel. It can contain echoed input,
repainted UI content, prior context, user-typed text, and arbitrary agent prose.
Marker-based result extraction from the transcript is therefore brittle: user
input can easily look like agent output, and terminal repaint behavior can hide or
reorder what the parent expects to see.

Instead, structured workflow results are reported out-of-band.

The workflow runtime uses a Unix domain socket result channel:

1. The parent creates a private temporary directory and Unix socket.
2. The parent generates a per-session token.
3. The parent launches the child with environment variables such as:

   ```text
   MYTEAM_RESULT_SOCKET=/path/to/result.sock
   MYTEAM_RESULT_TOKEN=<nonce>
   MYTEAM_RESULT_SCHEMA=<optional-json-schema-or-schema-name>
   ```

4. The agent is instructed to call a helper/tool when it has the final result.
5. The helper reads the env vars, connects to the socket, and sends newline-delimited JSON.
6. The parent validates the token and records the first valid result.
7. The parent queues an agent-specific exit sequence into the PTY session.
8. The parent waits for the PTY session to exit and returns the structured result
   plus diagnostics.

A simple message shape:

```json
{
  "version": 1,
  "kind": "result",
  "token": "...",
  "payload": {"answer": "..."}
}
```

The parent acknowledges receipt:

```json
{"ok": true}
```

The token is not meant to protect against the child process itself; the child is
the intended reporter and can read its own environment. The token prevents
accidental cross-session writes and makes malformed/stale reports easier to
reject.

## Result tool

The result tool is the child-facing command the agent calls when it is ready to
return the workflow step result. It is a local CLI helper backed by the socket
protocol above. Later, this can be adapted behind first-class tool systems such
as MCP or provider-native tools, but the CLI shape works with terminal-driven
agents today.

The tool is available on the child process `PATH`, or can be referenced with an
absolute path in the prompt. The command name is:

```bash
myteam workflow-result
```

or, if implemented as a Python module entrypoint:

```bash
python -m myteam.workflow.result_tool
```

The command reads connection details from the environment:

```text
MYTEAM_RESULT_SOCKET
MYTEAM_RESULT_TOKEN
```

The agent should not need to know the socket path or token values. It only needs
to call the tool with the payload.

### Calling the tool

The preferred interface supports JSON from stdin because it avoids shell
quoting issues:

```bash
myteam workflow-result <<'JSON'
{"answer":"The final answer","status":"complete"}
JSON
```

It also supports a `--json` argument for simple cases:

```bash
myteam workflow-result --json '{"answer":"The final answer","status":"complete"}'
```

For plain-text outputs, a convenience flag wraps text in a conventional
payload shape:

```bash
myteam workflow-result --text "The final answer"
```

which sends:

```json
{"text":"The final answer"}
```

The stdin JSON form should be the canonical one for structured workflow outputs.
It lets the prompt ask for exact JSON without requiring the agent to escape nested
quotes for the shell.

### Tool behavior

The tool:

1. read the payload from stdin, `--json`, or `--text`
2. parse and validate JSON when appropriate
3. read `MYTEAM_RESULT_SOCKET` and `MYTEAM_RESULT_TOKEN`
4. connect to the Unix socket
5. send one newline-delimited JSON message:

   ```json
   {
     "version": 1,
     "kind": "result",
     "token": "...",
     "payload": {"answer": "..."}
   }
   ```

6. wait for an acknowledgement from the parent
7. print a short confirmation and exit zero if the parent accepts the result

If the env vars are missing, the socket cannot be reached, the parent rejects the
token, or the payload is invalid, the tool should print a concise error to stderr
and exit non-zero.

The tool should not terminate the agent process directly. It only reports the
result. The parent decides what to do after receipt, usually by queueing the
backend-specific exit sequence into the PTY session.

### Prompting the agent to use the tool

Workflow prompts should instruct the agent to call the result tool instead of
printing result markers. The instruction should be explicit that terminal output
is not the return channel.

Example prompt fragment:

```text
When you have completed the objective, return the final workflow result by
calling this command exactly once:

  myteam workflow-result <<'JSON'
  <your JSON result here>
  JSON

Do not wrap the result in markdown fences. Do not print special result markers.
Do not merely describe the result in the terminal. The workflow runner only
receives the final structured result when you call `myteam workflow-result`.

The JSON you send must match this shape:

  {
    "answer": "..."
  }

After the command succeeds, wait for the session to close.
```

For a workflow with an output template, the prompt can include the expected JSON
schema or example:

```text
Your result must be valid JSON matching this template:

  {
    "summary": "string",
    "files_changed": ["string"],
    "needs_followup": false
  }

Submit it with:

  myteam workflow-result <<'JSON'
  {"summary":"...","files_changed":[],"needs_followup":false}
  JSON
```

The prompt should also clarify that the tool should be called only once. If the
agent discovers an error and cannot complete the objective, it can still call the
same tool with an error-shaped payload if the workflow schema allows it, for
example:

```json
{"status":"blocked","reason":"Missing credentials for the requested service"}
```

### First-class tool integration later

The CLI helper is only the initial transport. If an agent supports real tool
calls, the same result-channel protocol can be hidden behind a provider-specific
tool named something like `submit_workflow_result`.

The conceptual tool contract is:

```text
submit_workflow_result(payload: object) -> acknowledgement
```

The implementation detail remains the same: send the payload to the parent over
the per-session result socket.

## Orchestration layer

The workflow-level orchestration composes the pieces:

```text
parent creates result channel
parent launches PTY session with result-channel env vars
PTY session yields raw output bytes
TerminalRecording builds a transcript
agent calls result tool
result listener receives structured payload
parent queues exit sequence into PTY session
PTY session exits
workflow returns payload + exit code + transcript
```

The structured result should come from the result channel, not from terminal
scraping. The transcript and exit code are diagnostics.

If a result arrives but the child exits non-zero after the requested shutdown,
the workflow can still return the structured result while preserving the non-zero
exit code and transcript for debugging.

If the child exits without reporting a result, the workflow should report a
missing-result error and include the transcript as diagnostic context.

## Why this design

This design is motivated by several failure modes in terminal-driven agent
workflows:

- prompt/result markers in terminal output can be echoed, copied, or typed by the
  user
- terminal UIs repaint content, move cursors, and overwrite cells
- raw chunks do not necessarily align with semantic output boundaries
- newline submission behavior varies between agents and terminal UIs
- some agents require byte sequences such as `payload + right-arrow + carriage-return`
  rather than a simple trailing newline
- relying on terminal output for structured data mixes presentation with control

By separating transport, recording, and result reporting, each layer has a narrow
contract:

- PTY session: bytes in/out and process lifecycle
- recorder: bytes to rendered transcript
- result channel: structured payload delivery
- workflow runner: policy and orchestration

This keeps the base terminal code reusable while making workflow completion more
reliable.

## Implementation status

This design has now been implemented in the workflow runtime.

The relevant production files are:

- `src/myteam/workflow/terminal/pty_session.py`
- `src/myteam/workflow/terminal/recording.py`
- `src/myteam/workflow/terminal/result_channel.py`
- `src/myteam/workflow/terminal/session.py`
- `src/myteam/workflow/steps.py`
- `src/myteam/workflow/agents/backends.py`

The old handoff references to `watcher.py`, `terminal_types.py`,
`tty_wrapper.py`, and `step_executor.py` are obsolete for the current runtime.

### Agent-specific submit behavior

Do not assume that appending `\n` submits input correctly for all agents.

`../agents/backends.py` contains the existing Codex-specific submit behavior:

```python
PTY_RIGHT_ARROW = b"\x1b[C"
```

`CodexAdapter.encode_input(...)` strips trailing newline/carriage-return from the
payload and submits with:

```python
payload.encode("utf-8") + PTY_RIGHT_ARROW + b"\r"
```

This exists because simple newline submission can fail with paste-burst behavior
in some terminal UIs. The PTY layer should write exactly the bytes it is given;
agent-specific submit sequences belong in adapters or orchestration.

### Remaining follow-up

Future workflow work should build on the current result-channel design instead of
reintroducing terminal marker scraping.
