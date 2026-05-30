# Task Package

## Purpose

`src/myteam/tasks/` implements the `myteam start [task]` feature.

Its job is to:

- load and validate authored task files
- resolve task file paths for YAML, Python, and markdown task definitions
- resolve references between completed steps
- run each step through an interactive terminal-backed agent session
- collect the final structured step result through an out-of-band result channel
- stop on the first failing step and return completed step state

This package is intentionally split into two layers:

- `tasks/` owns task semantics
- `tasks/terminal/` owns terminal transport and result delivery

The task layer is further split so each file stays narrow:

- `definition/parser.py` loads authored YAML
- `definition/models.py` owns the task schema models and execution-time step models
- `resolution/reference_resolver.py` resolves `$step.path` references
- `execution/engine.py` handles multi-step orchestration
- `execution/steps.py` handles single-step execution and prompt/argv construction
- `execution/usage.py` owns usage tracking and reporting helpers

## Black-Box View

From outside the package, the flow is:

1. `commands.start(...)` resolves a task file path and either executes a Python task script or loads YAML.
2. `tasks.definition.load_task(...)` loads authored YAML and delegates schema checks to `tasks.validation`.
   `tasks.definition.load_markdown_task(...)` loads markdown task frontmatter and body text.
   If the frontmatter declares required input and the caller did not supply it, `commands.start(...)`
   reports an error before launching the task.
3. `tasks.execution.run_task(...)` executes steps in authored order.
4. For each step, `tasks.execution.run_agent(...)`:
   - receives the resolved step values from the engine
   - resolves the configured agent runtime config
   - builds the prompt
   - runs or resumes an interactive terminal session
   - waits for the agent to call `myteam task result` over the private result channel
   - validates the returned payload against the authored output shape
5. The engine stores completed step state for later `$step.path` references.
6. The engine returns either:
   - a completed task output mapping
   - or a failed result naming the first failed step

The path-resolution rule for `commands.start(...)` and `tasks.execution.run_named_task(...)`
is:

- if no extension is provided, prefer `.py`, then `.md`, then `.yaml`, then `.yml`
- if multiple matches exist at the same priority, continue with the prioritized target and emit a
  brief warning
- if an explicit extension is not one of `.py`, `.md`, `.yaml`, or `.yml`, treat it as an error

`tasks.execution.cli_commands.task_start(...)` is different: it only submits a child-task
request over the control channel. The parent task runner resolves the requested child task
name when it handles that request.

The terminal contract is:

- terminal output is for user-visible interaction and diagnostics
- structured workflow results are not scraped from terminal output
- the child reports its final result over a private Unix socket keyed by the step's session nonce
- `myteam task result` and `myteam task start` take `--session-nonce` so the agent can 
  submit against the active step without relying on hidden env state
- Python task authors can pass `session_id` to `run_agent(...)` to resume, set `fork=True`
  to fork that session, and read `StepResult.session_id` from completed steps that return one
- `run_agent(...)` launches agents from the detected project root by default; Python task
  authors can pass `cwd` to override the launch directory for a specific agent run

## File-Level Ownership

### Package Root

- [__init__.py](__init__.py)
  Exposes the main public task entrypoints: `run_agent`, `load_task`, `load_markdown_task`, and `run_task`.

- [definition/models.py](definition/models.py)
  Owns shared task types: authored step definitions, completed-step state, run results, and the pydantic models
  used to validate authored YAML step definitions.

- [definition/parser.py](definition/parser.py)
  Owns task-file loading and top-level orchestration around task schema validation.

- [resolution/reference_resolver.py](resolution/reference_resolver.py)
  Owns `$step.path` reference resolution against prior completed steps.

- [execution/engine.py](execution/engine.py)
  Owns multi-step orchestration, authored-order execution, fail-fast behavior, and completed-step storage.

- [execution/steps.py](execution/steps.py)
  Owns single-step execution: accept resolved step values, resolve agent runtime config, build prompt, run, resume, or fork a session, validate result, discover session id, and return `StepResult`.

- [execution/usage.py](execution/usage.py)
  Owns usage-tracking helpers and usage-summary formatting.

- [execution/cli_commands.py](execution/cli_commands.py)
  Owns the child-facing `myteam task start` and `myteam task result` command implementations.

- [execution/errors.py](execution/errors.py)
  Owns task execution error types.

- [execution/prompts.py](execution/prompts.py)
  Owns prompt-building helpers for single-step execution and child-task resumes.

- [resolution/session_resolution.py](resolution/session_resolution.py)
  Owns session id and project-root resolution helpers.

### Agents

- [agents/__init__.py](agents/__init__.py)
  Re-exports the agent lookup and runtime config helpers.

- [agents/registry.py](agents/registry.py)
  Owns the default agent name and compatibility lookup.

- [agents/runtime.py](agents/runtime.py)
  Owns resolution of optional project-local runtime config modules with fallback to packaged defaults.

- [agents/codex.py](agents/codex.py) and [agents/pi.py](agents/pi.py)
  Own packaged default runtime config modules for supported agents, including each agent's terminal input encoding, launch arguments, exit sequence, and session discovery.

### Terminal

- [terminal/__init__.py](terminal/__init__.py)
  Re-exports the terminal-layer building blocks.

- [terminal/pty_session.py](terminal/pty_session.py)
  Owns the low-level PTY transport. It launches the child, yields raw output bytes through the `events()` generator, mirrors terminal IO, and accepts injected input through `enqueue_input(...)`.

- [terminal/recording.py](terminal/recording.py)
  Owns transcript recording from raw PTY byte chunks.

- [terminal/result_channel.py](terminal/result_channel.py)
  Owns the out-of-band result socket, token validation, acknowledgement handling, and payload submission helper.

- [terminal/session.py](terminal/session.py)
  Owns orchestration of `PtySession`, `TerminalRecording`, and `ResultChannel` into one terminal session result for a task step.

## Design Constraints

- `PtySession.events()` is observation-only and yields raw `bytes`.
- Input injection uses `enqueue_input(...)`, not generator `.send(...)`.
- Structured results come from the result channel, not terminal scraping.
- `tasks/terminal/` should stay minimal and transport-focused.
