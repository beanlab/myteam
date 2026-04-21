# Design

## Purpose

This document describes the v1 high-level architecture for a lightweight workflow runner that executes sequential
agent-driven steps through a TTY-wrapped CLI session.

The design is intentionally minimal. It favors small modules, straightforward data flow, and a small set of
third-party libraries over a general workflow framework.

## Goals

- Read a YAML workflow definition.
- Execute steps in order.
- Let each step run an agent session through a PTY-backed wrapper.
- Detect when a step has produced its final structured output JSON.
- Store completed per-step runtime state for use by later steps.
- Support lightweight structured substitution from prior completed step state into later step inputs.
- Keep full per-step transcripts in memory for debugging.

## Non-Goals For V1

- DAG scheduling or parallel step execution
- Cross-run persistence or resume
- A plugin architecture
- Generic workflow language features
- JSONPath or other rich query languages
- Multiple agent backends beyond the initial Codex CLI path

## Core Design

The runtime is split into a small number of modules with clear boundaries:

- `workflow_parser`
- `workflow_engine`
- `step_executor`
- `agent_registry`
- `tty_wrapper`
- `reference_resolver`
- `models`

The engine remains deterministic and policy-light.
The executor owns step-specific runtime behavior.
The agent registry resolves lightweight agent-specific runtime settings.
The PTY wrapper only handles subprocess and stream transport.
Reference substitution is isolated so it can evolve later without disturbing the executor or engine.

## Module Boundaries

### `workflow_parser`

Responsibility:
- Load YAML workflow definitions.
- Validate the workflow structure.
- Validate authored step and key names required by the public workflow format.
- Validate referenced agent names before execution begins.
- Normalize workflow data into internal models.

Out of scope:
- Executing steps
- Resolving references
- Running subprocesses

Primary interface:
- `load_workflow(path) -> WorkflowDefinition`

Suggested libraries:
- `PyYAML`

Notes:
- For v1, simple `PyYAML` loading is sufficient.
- The parser may use `yaml.safe_load(...)` and should not try to enforce strict JSON syntax.
- The public workflow file format is a top-level mapping of `step_name: step_definition`.
- There is no `steps:` wrapper in v1.
- There are no workflow-level authored fields in v1.
- Step names must be valid Python-identifier-style names.
- Authored nested keys that participate in the workflow format and reference system should also use valid Python-identifier-style names.

## `workflow_engine`

Responsibility:
- Run steps in declared order.
- Maintain in-memory run state.
- Pass prior completed step state into later steps through the reference resolver.
- Call the step executor for each step.
- Stop on failure and return run results.

Out of scope:
- Prompt construction details
- PTY/session management
- Output parsing details

Primary interface:
- `run_workflow(workflow: WorkflowDefinition) -> WorkflowRunResult`

## `step_executor`

Responsibility:
- Execute one workflow step.
- Build the initial prompt for the step.
- Resolve the step input using prior step outputs.
- Define the completion contract for the session.
- Resolve which agent to use for the step.
- Call the PTY wrapper directly using the resolved agent config.
- Accumulate streamed output.
- Detect the final structured completion payload.
- Parse and validate the completed output.
- Retain the full raw transcript for the step result.

Out of scope:
- Workflow ordering
- PTY mechanics

Primary interface:
- `execute_step(step: StepDefinition, context: RunContext) -> StepResult`

Notes:
- In v1, the executor directly uses the PTY wrapper rather than introducing a separate agent session abstraction.
- The executor should stay mostly agnostic to the specific CLI agent being used.
- The step may specify an `agent` key.
- If `agent` is omitted, the executor uses the default shipped agent config, initially `codex`.
- A step's `input` field is a free-form structured object.
- The executor does not impose a fixed schema on `input` beyond recursively resolving supported references inside it.
- Interactive user-confirmation loops are out of scope for v1.
- The authored workflow is a top-level mapping keyed by step name.
- Each step definition contains `prompt`, optional `input`, optional `agent`, and required `output`.
- The executor uses one canonical prompt template in v1:
  - a fixed session instruction explaining the final JSON completion contract
  - an `Input:` section containing the resolved input as YAML when present
  - an `Objective:` section containing the step `prompt`
  - an `Output template:` section containing the authored `output` block as YAML
  - a final reminder to return only the completion JSON object when done
- The completion contract is exact: the agent must finish with only one parseable JSON object shaped like `{"status": "OBJECTIVE_COMPLETE", "content": ...}`.
- The executor treats `content` as the step output payload and validates it against the step's `output` template.
- Validation is structural only in v1.
- If the template shows a nested object at some location, the returned value at that location must be an object with the required nested keys.
- Otherwise, a template leaf is purely descriptive and the returned value may be any JSON value, including string, number, boolean, `null`, object, or array.
- Lists are not expected to appear in authored output templates in v1, and no special template-list validation semantics are defined.
- The executor provides an output handler to the wrapper, but the runner is passive after launch in v1.
- The handler should only detect completion from streamed output and otherwise return `None`.
- The executor keeps the full accumulated transcript in memory and may use that transcript as the completion-detection buffer.
- After each new chunk, if the accumulated transcript contains `OBJECTIVE_COMPLETE`, the executor attempts to parse the trailing portion of the transcript as exactly one top-level JSON object.
- Completion is accepted only if that parsed object matches `{"status":"OBJECTIVE_COMPLETE","content":...}`.
- If parsing fails, the executor continues reading output.
- After completion is detected, the executor asks the wrapper to send only the configured quit sequence.
- If additional output arrives after valid completion is accepted, that output is appended to the transcript but does not invalidate success. The first accepted valid completion object wins.
- Step failure in v1 includes:
  - reference resolution failure before launch
  - agent process launch failure
  - child session exit before valid completion JSON is seen
  - malformed final JSON
  - final JSON with the wrong top-level shape or missing required output keys
  - timeout or inactivity timeout

## `agent_registry`

Responsibility:
- Define known agent runtime configurations.
- Provide a built-in default `codex` configuration.
- Resolve the `agent` key from a step definition into an `AgentConfig`.
- Keep executable-specific settings out of the executor.

Out of scope:
- Workflow semantics
- Prompt construction
- Completion detection
- PTY process handling

Primary interface:
- `get_agent_config(name: str | None) -> AgentConfig`

Suggested model:

```python
@dataclass
class AgentConfig:
    name: str
    argv: list[str]
    exit_text: str | None
```

Notes:
- `argv` should be the full command vector, not just an executable name.
- The shipped default configuration should be equivalent to:

```python
AgentConfig(
    name="codex",
    argv=["codex"],
    exit_text="/quit\n",
)
```

- This module is intentionally small in v1.
- More agent-specific settings can be added later without changing the `workflow_engine` boundary.
- Unknown `agent` names should fail during workflow validation rather than at step execution time.
- Workflow-authored agent config overrides are out of scope for v1.

## `tty_wrapper`

Responsibility:
- Spawn the child agent process under a PTY.
- Forward streamed output to the caller.
- Accept an initial input string.
- Invoke a caller-provided output handler for child output.
- If the handler returns a string, write it to the child session.
- Handle terminal sizing, EOF, child exit, and shutdown.
- Enforce inactivity and graceful shutdown timing.

Out of scope:
- Workflow semantics
- Prompt construction
- Completion policy
- JSON parsing

Primary interface:

```python
run_pty_session(
    argv: list[str],
    initial_input: str | None,
    on_output: Callable[[bytes], str | None],
    *,
    quit_sequence: str | None = None,
    inactivity_timeout_seconds: int = 300,
    graceful_shutdown_timeout_seconds: int = 30,
) -> PtyRunResult
```

Notes:
- The wrapper should stay generic enough to support other CLI agents later.
- For v1, the interface stays minimal and uses `str | None` from the output handler instead of a richer command type.
- In v1, there is no fixed maximum step duration as long as the child continues to emit output within the inactivity window.
- No separate startup timeout is required beyond normal process launch failure handling.
- The wrapper should inherit working directory, environment variables, and terminal dimensions from the parent process.
- For v1, child processes run from the caller's current working directory.
- Timeout values are configured in code as workflow-layer global defaults, not authored in the workflow file and not configurable per step.
- The wrapper should launch the child inside a PTY using `pty.fork()` or equivalent PTY-backed subprocess behavior.
- The wrapper should copy the parent terminal window size into the child PTY before interaction begins.
- The wrapper should update the child PTY window size on parent `SIGWINCH` so interactive programs continue to render correctly after terminal resizes.
- If the wrapper is used in an interactive passthrough mode, it should require real TTY stdin/stdout on the parent side.
- In interactive passthrough mode, the wrapper should place parent stdin into raw/cbreak mode for the duration of the session and restore the original terminal settings on exit.
- The wrapper should drive IO with a `select`-style loop over parent input and PTY output so it can forward bytes in both directions without blocking.
- If parent input reaches EOF during an interactive session, the wrapper should close the PTY master and begin shutdown.
- Child output may need to be buffered across reads so the wrapper can safely detect completion markers or other output-triggered actions that may span chunk boundaries.
- If the wrapper supports output-triggered writes back into the child session, it should preserve any trailing partial-match suffix in the output buffer until enough bytes arrive to decide whether a trigger matched.
- When the child PTY closes, any remaining buffered output should be flushed before the wrapper returns.
- The wrapper should restore signal handlers, terminal state, and file descriptors in `finally`-style cleanup even when the child exits unexpectedly.
- The wrapper result should preserve the child's exit status using normal shell conventions: plain exit code for normal exit, `128 + signal` for signal termination.

## `reference_resolver`

Responsibility:
- Resolve lightweight references from prior completed step state into the current step input object.
- Keep substitution rules isolated from parsing and execution logic.

Out of scope:
- YAML parsing
- Workflow execution
- Rich query languages

Primary interface:
- `resolve_references(value: Any, prior_steps: dict[str, Any]) -> Any`

### V1 Reference Rules

References are exact-string placeholders only.

Example:

```yaml
input:
  review_context:
    previous:
      reason: $step1.output.best_haiku.reason
      text: $step1.output.best_haiku.haiku
```

Rules:
- `input` is a free-form object, list, or scalar value supplied by the workflow author.
- A string is treated as a reference only if the entire value matches the reference pattern.
- `$$` escapes a literal leading dollar for exact-string scalar values.
- The root token after `$` is the step name.
- Remaining tokens are dotted path components into that step's stored runtime object.
- The resolved value is inserted as structured data.
- Objects and arrays remain objects and arrays after insertion.
- Missing paths are errors.
- Reference traversal supports object keys only, not array indexes.
- Step names and referenceable keys must satisfy standard Python identifier rules so dotted paths are unambiguous.
- Reference validity is checked only when the step executes.
- Forward references, self-references, and misspelled step names are not rejected during workflow parsing.
- Each completed step is stored under its step name using a structure aligned with the authored workflow step plus the completed `output` value.
- This allows later steps to reference prior `input`, `prompt`, `agent`, and `output` fields when needed.

Non-goals for v1:
- JSONPath
- Filters
- Wildcards
- Partial string interpolation such as `"Winner: $step1.best_haiku.haiku"`
- Multi-match semantics
- Array indexing inside reference paths

This module exists as a separate boundary so richer lookup or templating behavior can be added later without changing
the engine or executor contract.

## `models`

Responsibility:
- Define shared internal data structures.

Expected models:
- `WorkflowDefinition`
- `StepDefinition`
- `WorkflowRunResult`
- `StepResult`
- `RunContext`
- `PtyRunResult`

Suggested shape:

```python
@dataclass
class StepDefinition:
    name: str
    prompt: str
    output: dict[str, Any]
    input: Any | None = None
    agent: str | None = None
```

Notes:
- `name` comes from the top-level workflow mapping key rather than a nested authored field.
- `output` is required and serves as the structural output template for validation.
- The runtime result models are informational/internal in v1 and are not part of the public workflow-file contract.

### `RunContext`

`RunContext` represents execution-time state supplied by the engine when executing a step.
It is distinct from `StepDefinition`, which contains the authored workflow configuration for that step.

For v1, `RunContext` should stay small and primarily carry prior completed step state:

```python
@dataclass
class RunContext:
    prior_steps: dict[str, Any]
    default_agent: str
```

Notes:
- `prior_steps` contains completed per-step runtime state keyed by step name.
- `default_agent` provides the fallback agent name when a step does not define its own `agent`.
- `RunContext` should not hold PTY handles, transcript buffers, or other step-internal execution state.
- If the executor is implemented as a class with injected dependencies, objects such as the agent registry do not need to live in `RunContext`.

Suggested result shape:

```python
@dataclass
class StepResult:
    step_name: str
    status: str
    output: Any | None = None
    error_type: str | None = None
    error_message: str | None = None
    transcript: str = ""
```

```python
@dataclass
class WorkflowRunResult:
    status: str
    steps: list[StepResult]
    failed_step_name: str | None = None
```

Notes:
- Every `StepResult` carries the full raw transcript in memory, regardless of success or failure.
- `status` values can remain simple strings in v1 as long as failure modes map cleanly into the explicit taxonomy above.

Suggested libraries:
- standard-library dataclasses

For v1, prefer standard-library dataclasses plus explicit validation logic over `pydantic`.

## Data Flow

1. The parser loads YAML and returns a validated workflow definition.
2. The engine iterates through workflow steps in order.
3. For each step, the executor asks the reference resolver to substitute any references using prior completed step state.
4. The executor builds the canonical prompt, including the fixed JSON completion instruction, resolved input, authored objective, and output template.
5. The executor resolves the step's `agent` key through the agent registry.
6. The executor calls the PTY wrapper with:
   - the resolved agent command
   - the initial input
   - an output handler
   - the resolved exit text
   - the inactivity timeout
   - the graceful shutdown timeout
7. The PTY wrapper streams output and passes it to the handler.
8. The executor handler passively watches the accumulated transcript for `OBJECTIVE_COMPLETE` and, once present, attempts to parse the trailing portion as a final JSON object matching `{"status": "OBJECTIVE_COMPLETE", "content": ...}`.
9. When completion is detected, the wrapper sends the quit sequence and allows up to 30 seconds for graceful exit.
10. Any trailing output after accepted completion is retained in the transcript but does not affect success.
11. The executor validates the `content` payload against the authored output template and returns a `StepResult` with transcript attached.
12. The engine stores the completed step state, including the authored step fields and completed output, and continues to the next step.
13. If any step fails, the engine stops immediately and returns a `WorkflowRunResult` naming the failing step.

## External Libraries

Recommended v1 dependencies:

- `PyYAML` for workflow loading

Avoid for v1:

- workflow orchestration frameworks
- JSONPath libraries
- templating systems unless prompt composition becomes more complex than simple string assembly
- `pydantic`

## Suggested Package Layout

```text
src/<package>/
  models.py
  workflow_parser.py
  workflow_engine.py
  step_executor.py
  agent_registry.py
  tty_wrapper.py
  reference_resolver.py
  cli.py
```

## CLI Surface

The v1 CLI should support running one workflow file.

Behavior:
- Quiet by default.
- Stream transcripts and step lifecycle details only when `--verbose` is enabled.
- Print nothing on success.
- Print the error and exit immediately on validation failure or execution failure.
- Exit with code `0` on success.
- Exit non-zero on validation failure or workflow execution failure.
- Do not emit a final human-readable summary in v1.

## Logging And Testing

Logging:
- Normal mode should surface only essential validation or execution failures.
- `--verbose` should log workflow and step lifecycle events, live PTY output, resolved step inputs, and parsed step outputs.
- Transcript retention is independent of log verbosity and always captured in memory on `StepResult`.

Testing:
- Require unit tests for `workflow_parser` and `reference_resolver`.
- Cover end-to-end workflow execution with integration tests against a deterministic local test agent rather than the real interactive CLI.
- The deterministic test agent should cover:
  - normal interaction with initial input, back-and-forth communication, valid completion JSON, exit-sequence handling, and brief trailing output after exit
  - agent exit before valid completion JSON is produced
  - malformed completion JSON
  - graceful shutdown behavior

## Open Extension Points

The following can be added later without disturbing the v1 boundaries too much:

- richer output-handler commands between executor and PTY wrapper
- richer reference syntax
- interpolation and templating
- alternate agent backends and additional agent settings
- persisted run state and resume
- per-step model and runtime settings
- step-generic prompt injection shared across workflow steps
- step-level `--exec` mode or other alternate execution modes

## Canonical Prompt Example

~~~text
I will give you an objective for this session.

When the objective is complete, your final output must be only a JSON object in this form:

{"status":"OBJECTIVE_COMPLETE","content":<filled result object>}

The `content` value must match the requested output structure.

Input:
```yaml
haikus:
  dogs: Dogs dream by the hearth
  cats: Cats vanish into dusk
  user_choice: Rain taps the porch rail
```

Objective:
Review the provided haikus.
Rank them in terms of which best captures the essence and style of haiku.

Output template:
```yaml
best_haiku:
  haiku: the selected haiku text
  reason: why this haiku was chosen
```

Return only the final JSON object when the objective is complete.
~~~
