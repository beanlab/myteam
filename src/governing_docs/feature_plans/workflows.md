# Workflow Runner Feature Plan

This document is the implementation design for the workflow feature.
It supersedes earlier exploratory design notes in `src/governing_docs/backlog/workflows.md`
where the two documents differ.

## Progress Notes

Completed:

- Interface document updated and committed.
- Feature plan created and refined to be the single design doc going forward.
- Framework refactor completed and committed:
  - `disclosure/`, `rosters/`, and `workflow/` package boundaries are in place
  - `utils.py` is now a compatibility layer over `disclosure`
- `agent_registry.py` sub-milestone completed and committed.
- `parser.py` sub-milestone completed and committed.
- Parser contract tests were added to capture the workflow file format as user-facing behavior.
- `reference_resolver.py` sub-milestone completed and committed.
- `tty_wrapper.py` sub-milestone completed and committed.
- Direct integration tests were added for `tty_wrapper.py` using a deterministic PTY child helper.
- A development-only monitored TTY prototype now lives under `scripts/prototypes/`.

Important decisions already made:

- `WorkflowDefinition` is a plain ordered mapping of `step_name -> step_definition`, not a list wrapper.
- Authored/config-shaped workflow data uses mapping-oriented types; internal runtime/result objects may still use dataclasses.
- Workflow output is one dictionary keyed by step name whose values mirror completed step state.
- Package source under `src/myteam/` should use package-relative imports.
- Exception: built-in loader entrypoints under `src/myteam/builtins/**/load.py` may keep absolute `myteam...` imports because they run as standalone scripts.
- The PTY wrapper should not take a separate `quit_sequence` kwarg; callback-returned text is written to the child PTY as input and should trigger normal child exit.
- Injected command text should be written first and the terminating Enter should be sent as a later keystroke, because Codex may treat a too-fast combined write as paste instead of command execution.

Next suggested sub-milestone:

- Implement `step_executor.py`.

## Context

`myteam` currently has a small, command-centric architecture:

- `src/myteam/cli.py` wires Fire command names to top-level functions.
- `src/myteam/commands.py` owns command behavior, validation, and user-facing error handling.
- `src/myteam/paths.py` owns narrow path-resolution helpers.
- Tests exercise the CLI as a black box by running `python -m myteam ...` and asserting on exit code, stdout, stderr, and filesystem state.

That structure is worth preserving. The new workflow feature adds a meaningful amount of behavior, but it does not require a broader CLI framework rewrite. The clean fit is:

- keep `myteam start <workflow>` as one more top-level command wired through `cli.py`
- keep user-facing command validation and exit behavior in `commands.py`
- organize existing and new domain logic into focused subpackages:
  - `src/myteam/disclosure/` for progressive-disclosure role/skill behavior
  - `src/myteam/workflow/` for workflow execution behavior
  - `src/myteam/rosters/` for roster listing, download, and update behavior

This follows the repo's existing pattern of keeping the CLI surface small while moving domain-specific behavior into dedicated helpers once the behavior becomes substantial.

## Chosen Design

### Why this approach

There are two plausible implementation strategies:

1. Put nearly all workflow behavior directly into `commands.py`.
2. Use thematic subpackages for disclosure, rosters, and workflow behavior while keeping `commands.py` as a thin command entry point.

The second approach is the better fit.

Reasons:

- The backlog design already identifies stable boundaries: parser, engine, executor, agent registry, PTY wrapper, reference resolver, and shared models.
- `commands.py` is already crowded enough that embedding streaming PTY control, YAML parsing, and reference resolution directly there would make the file harder to reason about.
- The test suite philosophy prefers public-command coverage, but some of the workflow rules are precise enough that they also need direct unit coverage. Small workflow modules make those tests straightforward.
- A dedicated `workflow/` subpackage gives us room to add future workflow features without bloating the existing role/skill command code.
- Keeping all workflow files together makes the feature easier to navigate than scattering new modules across `src/myteam/`.
- `disclosure/` is a better home for role/skill loading and listing than leaving that behavior spread across `commands.py` and `utils.py`, because those features are all about progressive disclosure from a local node.
- `rosters/` should become a real package instead of a single top-level module so remote roster behavior has a consistent home alongside the other domain areas.

### Framework assumptions to preserve

- Fire remains the CLI wiring mechanism.
- `commands.py` remains the place where command functions translate internal errors into user-visible stderr and exit codes.
- `commands.py` should contain only minimal plumbing across disclosure, roster, and workflow startup, not domain business logic.
- Package source files under `src/myteam/` should use package-relative imports rather than absolute `myteam...` imports.
- Exception: built-in loader entrypoints under `src/myteam/builtins/**/load.py` may continue using absolute `myteam...` imports because they are executed as standalone loader scripts.
- Project-local root selection continues to flow through `_selected_root(prefix)`.
- Workflow file lookup should behave like other local-tree features: relative to the selected root and supporting slash-delimited names.
- High-level CLI tests remain the primary evidence for public behavior.

## Framework Refactor

This phase prepares the codebase for the workflow feature without yet delivering the full feature.

### 1. Repackage existing domain logic by theme

Files:

- `src/myteam/disclosure/__init__.py`
- `src/myteam/disclosure/...`
- `src/myteam/rosters/__init__.py`
- `src/myteam/rosters/...`
- `src/myteam/commands.py`
- `src/myteam/utils.py`

Changes:

- Move role/skill disclosure behavior into `disclosure/`.
- Move roster behavior from `src/myteam/rosters.py` into a `rosters/` package.
- Update imports so `commands.py` depends on those packages rather than holding or reaching into their internals directly.
- Keep public CLI behavior unchanged during this reorganization.

Why:

- This is the right moment to organize the code around stable product concepts before adding another major feature.
- The workflow feature will otherwise increase the amount of cross-domain logic in `commands.py`.
- Doing the packaging cleanup first makes subsequent workflow work easier to place cleanly.

### 2. Extend path helpers to support workflow lookup

Files:

- `src/myteam/paths.py`

Changes:

- Add a helper that resolves a workflow name under the selected local root.
- Add a helper that searches for a workflow file using supported YAML extensions.
- Keep this helper narrowly focused on path resolution, not validation of workflow contents.

Why:

- The existing code already centralizes local-root handling in `paths.py`.
- `myteam start` should reuse the same root-selection rules as `get`, `new`, and `remove`.
- Isolating file lookup rules avoids duplicating extension-search logic in command handlers and tests.

### 3. Introduce shared workflow models

Files:

- `src/myteam/workflow/models.py`

Changes:

- Add the shared type/module boundary in `workflow/models.py`.
- Define the core internal model names the workflow modules will depend on.
- It is fine to add placeholder or partial model definitions here as long as they do not introduce runnable workflow behavior yet.

Why:

- Authored workflow data is YAML/JSON-shaped and is simpler to validate and traverse as mappings.
- Config-shaped workflow data should also stay mapping-oriented when it may come from YAML later.
- Internal runtime and result objects still benefit from dataclass structure.
- Defining those contracts up front keeps later modules simple and explicit.

### 4. Add workflow package boundaries

Files:

- `src/myteam/workflow/agent_registry.py`
- `src/myteam/workflow/parser.py`
- `src/myteam/workflow/reference_resolver.py`
- `src/myteam/workflow/tty_wrapper.py`

Changes:

- Add the module boundaries and public function entry points the feature implementation will fill in later.
- Keep these files as framework scaffolding during the refactor phase rather than implementing full workflow behavior yet.

Why:

- The backlog design treats these as separate concerns with stable boundaries.
- Creating the boundaries first makes the later feature implementation simpler and keeps workflow behavior out of unrelated files.

### Refactor completion criteria

At the end of the framework-refactor phase:

- The new workflow support modules exist with stable boundaries.
- Existing disclosure and roster behavior has been moved into thematic packages without changing CLI behavior.
- Existing non-workflow commands behave exactly as before.
- Existing tests should still pass without changing their assertions.
- The workflow-specific modules may still be placeholders as long as they establish the intended structure without shipping user-visible workflow behavior.

## Feature Addition

This phase uses the refactored framework to add the actual `myteam start` feature.

### 1. Implement workflow parsing, agent lookup, reference resolution, and PTY wrapper behavior

Files:

- `src/myteam/workflow/parser.py`
- `src/myteam/workflow/agent_registry.py`
- `src/myteam/workflow/reference_resolver.py`
- `src/myteam/workflow/tty_wrapper.py`

Changes:

- `parser.py`
  - Load YAML from a resolved workflow path using `yaml.safe_load(...)`.
  - Validate the top-level workflow shape.
  - Validate each step's required and optional keys.
  - Validate identifier-style step names and relevant authored nested keys.
  - Validate that authored agent names are known.
  - Preserve authored step order.
  - Reject workflow-level authored fields outside the top-level step mapping.
- `agent_registry.py`
  - Add a built-in default `codex` agent configuration.
  - Add lookup for workflow-authored `agent` names.
- `reference_resolver.py`
  - Implement exact-string reference substitution for structured `input` data.
  - Support `$step.key.path` references and `$$` escaping.
  - Reject missing paths and unsupported traversal cases.
- `tty_wrapper.py`
  - Implement the generic PTY-backed subprocess runner.
  - Accept initial input and a caller-provided output handler.
  - Write any non-`None` string returned from `on_output` back to the child PTY as input.
  - Return transcript and child exit status with inactivity/graceful-shutdown handling.

Why:

- These modules define the actual workflow behavior; they are not feature-neutral scaffolding.
- Grouping them together as the first feature-implementation sub-milestone makes the later executor and command work straightforward.

### 2. Add workflow execution modules

Files:

- `src/myteam/workflow/step_executor.py`
- `src/myteam/workflow/engine.py`

Changes:

- `step_executor.py`
  - Resolve a step's `input` using prior completed step state.
  - Build the canonical agent prompt from authored `input`, `prompt`, and `output`.
  - Run the configured agent through the PTY wrapper.
  - Detect the final completion payload in streamed output.
  - Parse the final JSON object from the transcript and include the parsed `content` payload in the returned `StepResult`.
  - Validate the returned output against the authored `output` template.
  - Return a `StepResult` with full transcript.
- `engine.py`
  - Execute steps in authored order.
  - Maintain prior completed step state.
  - Stop at the first failing step.
  - Return a `WorkflowRunResult` that exposes the final workflow `output` and names the failing step when applicable.

Why:

- This keeps orchestration logic and step-specific runtime behavior separate.
- The engine can stay deterministic and small.

### 3. Add the public `start` command

Files:

- `src/myteam/commands.py`
- `src/myteam/cli.py`

Changes:

- Add `start(workflow: str, prefix: str = DEFAULT_LOCAL_ROOT, verbose: bool = False)`.
- Resolve the workflow file from the selected local root.
- Call the parser and engine.
- Translate parser/runtime failures into the documented stderr + non-zero exit behavior.
- Keep normal successful execution quiet by default.
- Add `start` to the Fire command table.

Why:

- This is the public interface promised in `application_interface.md`.
- The command should remain thin and delegate workflow-specific mechanics into the `workflow/` subpackage.

### 4. Support verbose execution output

Files:

- likely `src/myteam/commands.py`
- possibly `src/myteam/workflow/engine.py` or `src/myteam/workflow/step_executor.py`

Changes:

- Add a minimal logging/reporting path for `--verbose`.
- Keep default success output quiet.
- Ensure validation and execution failures still surface clearly in normal mode.

Why:

- The backlog design defines quiet-by-default CLI behavior.
- Verbose output is part of the public workflow command behavior and should not be bolted on later.

### 5. Add tests that match the documented interface

Files:

- new CLI-flow test file for workflow start behavior, likely `tests/test_workflow_flow.py`
- `tests/test_version_and_list_flow.py` or another command-availability test file if needed
- direct unit tests for parser/reference logic, likely:
  - `tests/test_workflow_parser.py`
  - `tests/test_reference_resolver.py`

Changes:

- Add CLI tests for:
  - successful `myteam start <workflow>`
  - `--prefix` workflow lookup
  - supported YAML extensions
  - malformed workflow failure
  - fail-fast behavior when a step fails
  - missing workflow file failure
- Add unit tests for:
  - parser structure validation
  - identifier validation
  - agent-name validation
  - reference substitution
  - escaping and missing-path errors
- Use a deterministic local test agent for integration tests instead of the real Codex CLI.

Why:

- The test suite philosophy centers public CLI behavior.
- Parser and reference semantics are detailed enough to merit direct unit coverage.

### 6. Update docs surfaced to users

Files:

- `README.md` if the CLI command list or usage examples need updating

Changes:

- Document `myteam start` usage if the current README describes the CLI surface.

Why:

- The conclusion process requires user-facing documentation to match shipped behavior.

## Implementation Notes

### Workflow-file lookup

- Resolve workflow names relative to `_selected_root(prefix)`.
- Support `.yaml` and `.yml` via a helper rather than hard-coding this in the command.
- Treat no match or multiple ambiguous matches as command-level errors.

### Parser contract

- The authored workflow file format is a top-level mapping of `step_name: step_definition`.
- There is no `steps:` wrapper.
- There are no workflow-level authored fields.
- Step definitions contain required `prompt`, required `output`, and optional `input` and `agent`.
- Step names must use Python-identifier-style names.
- Authored nested keys that participate in workflow/reference structure should also use identifier-style names.

### Agent registry contract

- The default shipped agent is `codex`.
- The default config should include:
  - `name: "codex"`
  - `argv: ["codex"]`
  - `exit_text: "/quit\n"`
- Unknown `agent` names should fail during workflow validation rather than later at execution time.
- Workflow-authored agent config overrides are out of scope.

### Executor prompt and completion contract

- The executor should stay mostly agnostic to the specific CLI agent being used.
- `input` is a free-form structured object; the executor should not impose schema beyond recursive reference resolution.
- The executor should use one canonical prompt template:
  - a fixed instruction explaining the final JSON completion contract
  - an `Input:` section containing resolved input as YAML when present
  - an `Objective:` section containing the step `prompt`
  - an `Output template:` section containing the authored `output` block as YAML
  - a final reminder to return only the completion JSON object when done
- Completion is exact: the agent must finish with one parseable JSON object shaped like `{"status": "OBJECTIVE_COMPLETE", "content": ...}`.
- The executor should treat `content` as the step output payload and validate it against the authored `output` template.
- Completion detection should use the accumulated transcript buffer.
- After each new chunk, if the transcript contains `OBJECTIVE_COMPLETE`, the executor should attempt to parse the trailing portion as exactly one top-level JSON object.
- Completion is accepted only if that object has the exact required top-level shape.
- If parsing fails, execution continues and the executor keeps reading output.
- If additional output arrives after valid completion is accepted, append it to the transcript but do not invalidate success.
- The first accepted valid completion object wins.
- The PTY wrapper does not parse completion payloads; the executor is responsible for parsing the final JSON object from the transcript and returning the parsed result in `StepResult`.

### Step state shape for references

Completed step state should be stored under the authored step name in a structure that exposes:

- `prompt`
- `input`
- `agent`
- `output`

This should be represented as a mapping-oriented typed structure rather than a nested dataclass, because reference traversal is keyed by authored field names and should stay close to the decoded workflow data.

The overall workflow output should likewise be represented as one dictionary keyed by step name whose values are that completed step-state structure.

Reference resolver rules:

- References are exact-string placeholders only.
- A string is treated as a reference only if the entire string value matches the reference pattern.
- `$$` escapes a literal leading dollar for exact-string scalar values.
- The root token after `$` is the step name.
- Remaining dotted tokens traverse object keys within that step's stored completed state.
- Resolved values are inserted as structured data.
- Objects and arrays remain objects and arrays after insertion.
- Missing paths are errors.
- Array indexing is not supported.
- Forward references, self-references, and misspelled step names are checked only when the step executes, not during initial parse.

Non-goals for reference resolution:

- JSONPath
- filters
- wildcards
- partial string interpolation
- multi-match semantics
- array indexing

### Output-template validation

Validation should be structural only:

- nested mappings in the template require nested mappings and required keys in the returned value
- leaf template values are descriptive only and do not constrain runtime scalar type

This keeps the public file format simple and aligned with the documented example.

- Lists are not expected in authored output templates for this feature phase, and no special list-template semantics are needed.

### Error handling

The public command should distinguish at least these user-visible failure classes:

- workflow file not found
- workflow parse/validation error
- reference resolution error
- step execution failure

All of them should produce a clear stderr message and a non-zero exit code.

Step failure should include at least:

- reference resolution failure before launch
- agent process launch failure
- child session exit before valid completion JSON is seen
- malformed final JSON
- final JSON with the wrong top-level shape or missing required output keys
- timeout or inactivity timeout

### Workflow run result shape

`WorkflowRunResult` should expose the workflow's final output payload directly as `output`, where that payload is the workflow output dictionary keyed by step name.

Why:

- The public command cares about the final workflow outcome, not a full internal trace structure.
- Per-step details can still exist in executor-local or debug-only structures without becoming the primary engine result contract.

### PTY wrapper contract

`run_pty_session` should not take a separate `quit_sequence` keyword argument.

The wrapper should expose one output-triggered write path: `on_output` returns `str | None`, and the wrapper writes any returned string to the child PTY as input.

When the executor detects completion, it should return the agent's configured exit text from `on_output`. That input should cause the agent session to exit, and the wrapper should conclude when the child process actually exits.

Why:

- That keeps subprocess IO control in one place instead of splitting it across callback behavior and a second wrapper parameter.
- The executor can still use the resolved agent config to decide what string to return when completion is detected.
- Wrapper completion stays grounded in normal child-process lifecycle rather than a second, wrapper-owned completion signal.

Additional PTY wrapper details:

- The wrapper should stay generic enough to support other CLI agents later.
- Child processes should run from the caller's current working directory.
- The wrapper should inherit the parent environment and terminal dimensions.
- Timeout values are configured in code as workflow-layer global defaults, not authored per workflow step.
- No separate startup timeout is required beyond normal process launch failure handling.
- There is no fixed maximum step duration as long as the child continues to emit output within the inactivity window.
- The wrapper should launch the child inside a PTY and copy the parent terminal size before interaction begins.
- The wrapper should update child PTY window size on parent `SIGWINCH`.
- IO should be driven by a `select`-style loop over parent input and PTY output.
- If parent input reaches EOF in an interactive mode, the wrapper should close the PTY master and begin shutdown.
- Child output may need buffering across reads so completion markers or output-triggered writes can match across chunk boundaries.
- If output-triggered writes are supported, the wrapper should preserve trailing partial-match suffixes until enough bytes arrive to decide whether a trigger matched.
- When the child PTY closes, any remaining buffered output should be flushed before returning.
- Cleanup should restore signal handlers, terminal state, and file descriptors even on unexpected exit.
- The wrapper result should preserve child exit status using normal shell conventions: raw exit code for normal exit, `128 + signal` for signal termination.

### Data flow

1. The parser loads YAML and returns a validated workflow definition.
2. The engine iterates through steps in authored order.
3. For each step, the executor resolves any references against prior completed step state.
4. The executor builds the canonical prompt from the fixed completion contract, resolved input, authored objective, and output template.
5. The executor resolves the step's `agent` through the agent registry.
6. The executor calls the PTY wrapper with the resolved agent command, initial input, output handler, and timeout settings.
7. The PTY wrapper streams output and passes chunks to the handler.
8. The executor watches the accumulated transcript for completion and, once accepted, returns the agent exit text from `on_output`.
9. The wrapper writes that text to the child PTY as input and then concludes when the child exits.
10. The executor validates the accepted `content` payload against the authored output template and returns a `StepResult`.
11. The engine stores completed step state under the step name using the authored step fields plus completed `output`.
12. If a step fails, the engine stops immediately and returns a failed `WorkflowRunResult`.
13. Otherwise, once all steps complete, the engine returns the final workflow output mapping keyed by step name.

### Logging and testing details

Logging:

- Normal mode should surface only essential validation or execution failures.
- `--verbose` should log workflow and step lifecycle events, live PTY output, resolved step inputs, and parsed step outputs.
- Transcript retention is independent of log verbosity and always captured in memory on `StepResult`.

Testing:

- Require unit tests for parser and reference resolver behavior.
- Cover end-to-end workflow execution with integration tests against a deterministic local test agent rather than the real interactive CLI.
- The deterministic test agent should cover:
  - normal interaction with initial input, back-and-forth communication, valid completion JSON, exit-trigger handling, and brief trailing output after exit
  - agent exit before valid completion JSON is produced
  - malformed completion JSON
  - graceful shutdown behavior

## Files Expected To Change

Framework refactor:

- `src/myteam/disclosure/__init__.py`
- `src/myteam/disclosure/...`
- `src/myteam/paths.py`
- `src/myteam/rosters/__init__.py`
- `src/myteam/rosters/...`
- `src/myteam/workflow/__init__.py`
- `src/myteam/workflow/models.py`
- `src/myteam/workflow/agent_registry.py`
- `src/myteam/workflow/parser.py`
- `src/myteam/workflow/reference_resolver.py`
- `src/myteam/workflow/tty_wrapper.py`

Feature addition:

- `src/myteam/cli.py`
- `src/myteam/commands.py`
- `src/myteam/workflow/step_executor.py`
- `src/myteam/workflow/engine.py`
- `tests/test_workflow_flow.py`
- `tests/test_workflow_parser.py`
- `tests/test_reference_resolver.py`
- `README.md` if needed

## Out Of Scope

The following should not be pulled into this branch unless implementation proves they are strictly required:

- parallel step execution
- resume or persisted workflow runs
- rich templating or partial string interpolation
- array indexing in references
- workflow-level metadata fields
- workflow authoring commands such as `myteam new workflow`
- alternate agent backends beyond the initial shipped agent registry
