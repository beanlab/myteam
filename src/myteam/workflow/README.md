# Workflow Package

## Purpose

`src/myteam/workflow/` implements the `myteam start <workflow>` feature.

Its job is to:

- load and validate authored workflow files
- resolve references between completed steps
- run each step through an interactive terminal-backed agent session
- collect the final structured step result through an out-of-band result channel
- stop on the first failing step and return completed step state

This package is intentionally split into two layers:

- `workflow/` owns workflow semantics
- `workflow/terminal/` owns terminal transport and result delivery

## Black-Box View

From outside the package, the flow is:

1. `commands.start(...)` resolves a workflow file path.
2. `workflow.parser.load_workflow(...)` loads and validates the authored YAML.
3. `workflow.engine.run_workflow(...)` executes steps in authored order.
4. For each step, `workflow.steps.run_agent(...)`:
   - receives the resolved step values from the engine
   - resolves the configured agent runtime config
   - builds the prompt
   - runs or resumes an interactive terminal session
   - waits for the agent to call `myteam workflow-result`
   - validates the returned payload against the authored output shape
5. The engine stores completed step state for later `$step.path` references.
6. The engine returns either:
   - a completed workflow output mapping
   - or a failed result naming the first failed step

The terminal contract is:

- terminal output is for user-visible interaction and diagnostics
- structured workflow results are not scraped from terminal output
- the child reports its final result over a private Unix socket
- Python workflow authors can pass `session_id` to `run_agent(...)` to resume, set `fork=True`
  to fork that session, and read `StepResult.session_id` from completed steps that return one
- `run_agent(...)` launches agents from the detected project root by default; Python workflow
  authors can pass `cwd` to override the launch directory for a specific agent run

## File-Level Ownership

### Package Root

- [__init__.py](__init__.py)
  Exposes the main public workflow entrypoints: `run_agent`, `load_workflow`, and `run_workflow`.

- [parser.py](parser.py)
  Owns workflow-file loading and validation of the authored YAML structure.

- [models.py](models.py)
  Owns shared workflow types: authored step definitions, completed-step state, and run results.

- [reference_resolver.py](reference_resolver.py)
  Owns `$step.path` reference resolution against prior completed steps.

- [engine.py](engine.py)
  Owns multi-step orchestration, authored-order execution, fail-fast behavior, and completed-step storage.

- [steps.py](steps.py)
  Owns single-step execution: accept resolved step values, resolve agent runtime config, build prompt, run, resume, or fork a session, validate result, discover session id, and return `StepResult`.

- [result_tool.py](result_tool.py)
  Owns the child-facing `myteam workflow-result` command implementation.

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
  Owns orchestration of `PtySession`, `TerminalRecording`, and `ResultChannel` into one terminal session result for a workflow step.

## Design Constraints

- `PtySession.events()` is observation-only and yields raw `bytes`.
- Input injection uses `enqueue_input(...)`, not generator `.send(...)`.
- Structured results come from the result channel, not terminal scraping.
- `workflow/terminal/` should stay minimal and transport-focused.
