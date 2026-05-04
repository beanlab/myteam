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

`recording.py` contains `TerminalRecording`, which consumes raw PTY bytes and
builds a rendered transcript.

The recording layer is intentionally separate from the PTY session. The PTY
session only transports bytes; the recorder interprets those bytes as terminal
output.

`TerminalRecording` uses `pyte` to maintain a virtual terminal screen. Its
recording model is scrollback-oriented:

- content that scrolls off the top of the terminal is appended to the transcript
- the current visible terminal screen is appended after the scrolled history when
  a snapshot is requested
- content overwritten in place is not preserved as a separate historical state

This gives a useful debugging transcript without pretending to be a full replay
log. It records what the user would have seen as the terminal advanced.

Example:

```python
recording = TerminalRecording(columns=80, lines=24)

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

Instead, structured workflow results should be reported out-of-band.

The proposed prototype is a Unix domain socket result channel:

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

The parent can acknowledge receipt:

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

The tool should be available on the child process `PATH`, or referenced with an
absolute path in the prompt. A prototype command name could be:

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

The preferred interface should support JSON from stdin because it avoids shell
quoting issues:

```bash
myteam workflow-result <<'JSON'
{"answer":"The final answer","status":"complete"}
JSON
```

It can also support a `--json` argument for simple cases:

```bash
myteam workflow-result --json '{"answer":"The final answer","status":"complete"}'
```

For plain-text outputs, a convenience flag could wrap text in a conventional
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

The tool should:

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

## Implementation handoff notes

A fresh session taking over this work should start by reading this file, then the
current prototypes:

- `pty_session.py`
- `recording.py`
- `watcher.py`
- legacy `session.py`
- `../agents/backends.py`

The current direction is experimental. The newer PTY/session work is not yet
wired into the older workflow runner.

### Current prototype state

`pty_session.py` currently defines the low-level `PtySession` class. It has been
simplified so that:

- `events()` yields raw `bytes`
- `events()` returns the child process exit code as an `int`
- it does not return `PtyRunResult`
- it does not yield `PtyOutputEvent`
- it does not track transcripts
- it does not expose the raw PTY master fd
- it still exposes `process` for R&D/debugging
- `run_core_pty_session_events` was removed
- module-level `__all__` was removed
- the `__main__` block is scratch/demo code and is not production-ready

`recording.py` currently defines `TerminalRecording`. It consumes raw PTY bytes
and returns a rendered transcript string:

```python
recording = TerminalRecording(columns=80, lines=24)
transcript = recording.feed(chunk)
```

`terminal_types.py` no longer has `TerminalSnapshot`. `NormalizedOutput.snapshot`
is now a plain `str`. The older PTY compatibility types still exist because the
legacy session layer uses them:

- `PtyRunResult`
- `PtyOutputEvent`
- `PtyWriteCommand`
- `PtySessionCommand`

Do not remove those older types until the older workflow/session code has been
migrated.

`watcher.py` is a scratch prototype. It currently still looks for marker strings
in the rendered terminal output. That approach is known to be brittle and should
be replaced by the result-tool/socket design described above.

### Legacy session layer

`session.py` is the older, more complex PTY wrapper used by existing tests and
workflow code. It still owns behavior such as:

- timeout handling
- transcript tracking
- `PtyOutputEvent`
- `PtyWriteCommand`
- `PtyRunResult`
- graceful shutdown command metadata

The newer `PtySession` should not be assumed to have replaced this layer yet.
Migration should be explicit and test-driven.

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

### Recommended next implementation steps

1. Add queued input to `PtySession`.

   Add a public method like:

   ```python
   session.enqueue_input(data: bytes) -> None
   ```

   Internally use an input queue plus wakeup pipe. The PTY loop should select on
   the wakeup pipe, drain queued input, and write the queued bytes to the PTY
   master from inside the session loop.

2. Change `PtySession.events()` to observation-only.

   The generator should not expect input via `.send(...)`. It should be typed as:

   ```python
   Generator[bytes, None, int]
   ```

   External callers inject input through `enqueue_input(...)`.

3. Add environment support to `PtySession`.

   The result channel needs to launch the child with additional environment
   variables. Add an optional constructor argument such as:

   ```python
   env: Mapping[str, str] | None = None
   ```

   and pass it to `subprocess.Popen(..., env=env)`.

4. Prototype `ResultChannel`.

   Likely new file:

   ```text
   result_channel.py
   ```

   Responsibilities:

   - create a private temporary directory
   - create a Unix domain socket path
   - generate a per-session token
   - expose environment variables for the child
   - listen for result messages
   - validate the token
   - store the first valid payload
   - acknowledge accepted/rejected messages

5. Implement the result tool.

   Likely command:

   ```bash
   myteam workflow-result
   ```

   Preferred call form:

   ```bash
   myteam workflow-result <<'JSON'
   {"answer":"..."}
   JSON
   ```

   The tool should read the socket path and token from the environment, send the
   payload as newline-delimited JSON, wait for acknowledgement, and exit zero only
   if the parent accepts the result.

6. Replace `watcher.py` marker scraping.

   The watcher/orchestrator should compose:

   - `ResultChannel`
   - `PtySession`
   - `TerminalRecording`

   Flow:

   ```text
   create result channel
   launch PTY session with result-channel env vars
   feed PTY output to TerminalRecording
   receive structured result over socket
   enqueue backend exit sequence into PTY session
   wait for child exit
   return result payload + exit code + transcript
   ```

### Open design decisions

- Should `PtySession` remain a minimal transport that returns only exit code?
  Current preference: yes. Recording and structured results belong above it.

- Should the result listener use a background thread or be integrated into a
  larger select loop? Current prototype preference: background listener thread +
  `session.enqueue_input(...)`. Longer-term, a unified event loop may be cleaner.

- What happens if multiple result messages arrive? Current preference: accept the
  first valid result, then reject or ignore later messages.

- Where should schema validation happen? Current preference: parent/orchestrator
  validates. The tool should at least validate that the payload is syntactically
  valid JSON.

- What happens if a result arrives but the child does not exit after the queued
  exit sequence? The orchestration layer needs a graceful shutdown timeout,
  followed by terminate/kill if needed. Preserve the result, exit diagnostics,
  and transcript.

### Useful checks

The recent relevant checks were:

```bash
python -m py_compile src/myteam/workflow/terminal/pty_session.py
python -m py_compile src/myteam/workflow/terminal/recording.py
pytest -q tests/test_terminal_recording.py tests/test_terminal_normalizer.py tests/test_backend_adapters.py tests/test_tty_wrapper.py
```

At the time these notes were written, the relevant tests passed.
