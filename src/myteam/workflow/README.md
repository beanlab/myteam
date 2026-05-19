# Workflow Package

## Purpose

`src/myteam/workflow/` supports Python workflow scripts that use `myteam start <workflow>` and
`myteam workflow-result`.

This package is intentionally split into two layers:

- `workflow/` owns workflow semantics
- `workflow/terminal/` owns terminal transport and result delivery

The workflow layer is further split so each file stays narrow:

- `steps.py` handles single-step execution and prompt/argv construction
- `usage.py` owns usage tracking and reporting helpers
- `validation/step_validation.py` owns execution-time step validation

## Black-Box View

From outside the package, the flow is:

1. `commands.start(...)` resolves a workflow path to a Python script and executes it in a
   separate Python process.
2. Python workflow code can call `workflow.steps.run_agent(...)` to launch an agent session.
3. The child agent reports its structured result through `myteam workflow-result`.
4. `workflow.steps.run_agent(...)`:
   - resolves the configured agent runtime config
   - builds the prompt
   - runs or resumes an interactive terminal session
   - waits for the agent to call `myteam workflow-result` over the private result channel
   - validates the returned payload against the authored output shape

The terminal contract is:

- terminal output is for user-visible interaction and diagnostics
- structured workflow results are not scraped from terminal output
- the child reports its final result over a private Unix socket using `MYTEAM_RESULT_SOCKET` and
  `MYTEAM_RESULT_TOKEN`
- Python workflow authors can pass `session_id` to `run_agent(...)` to resume, set `fork=True`
  to fork that session, and read `StepResult.session_id` from completed steps that return one
- `run_agent(...)` launches agents from the detected project root by default; Python workflow
  authors can pass `cwd` to override the launch directory for a specific agent run

## File-Level Ownership

### Package Root

- [__init__.py](__init__.py)
  Exposes the main public workflow entrypoint: `run_agent`.

- [models.py](models.py)
  Owns shared runtime types such as `StepResult` and `UsageInfo`.

- [steps.py](steps.py)
  Owns single-step execution: accept resolved step values, resolve agent runtime config, build
  prompt, run, resume, or fork a session, validate result, discover session id, and return
  `StepResult`.

- [usage.py](usage.py)
  Owns usage-tracking helpers and usage-summary formatting.

- [validation/step_validation.py](validation/step_validation.py)
  Owns runtime validation for step execution arguments and returned step output.

- [result_tool.py](result_tool.py)
  Owns the child-facing `myteam workflow-result` command implementation.

### Agents

- [agents/__init__.py](agents/__init__.py)
  Re-exports the agent lookup and runtime config helpers.

- [agents/registry.py](agents/registry.py)
  Owns the default agent name and compatibility lookup.

- [agents/runtime.py](agents/runtime.py)
  Owns resolution of optional project-local runtime config modules with fallback to packaged
  defaults.

- [agents/codex.py](agents/codex.py) and [agents/pi.py](agents/pi.py)
  Own packaged default runtime config modules for supported agents, including each agent's terminal
  input encoding, launch arguments, exit sequence, and session discovery.

### Terminal

- [terminal/__init__.py](terminal/__init__.py)
  Re-exports the terminal-layer building blocks.

- [terminal/pty_session.py](terminal/pty_session.py)
  Owns the low-level PTY transport. It launches the child, yields raw output bytes through the
  `events()` generator, mirrors terminal IO, and accepts injected input through `enqueue_input(...)`.

- [terminal/recording.py](terminal/recording.py)
  Owns transcript recording from raw PTY byte chunks.

- [terminal/result_channel.py](terminal/result_channel.py)
  Owns the out-of-band result socket, token validation, acknowledgement handling, and payload
  submission helper.

- [terminal/session.py](terminal/session.py)
  Owns orchestration of `PtySession`, `TerminalRecording`, and `ResultChannel` into one terminal
  session result for a workflow step.

## Design Constraints

- `PtySession.events()` is observation-only and yields raw `bytes`.
- Input injection uses `enqueue_input(...)`, not generator `.send(...)`.
- Structured results come from the result channel, not terminal scraping.
- `workflow/terminal/` should stay minimal and transport-focused.
