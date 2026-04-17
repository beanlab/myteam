# Workflow Runner Feature Plan

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

- Add dataclasses for:
  - `StepDefinition`
  - `WorkflowDefinition`
  - `RunContext`
  - `StepResult`
  - `WorkflowRunResult`
  - `PtyRunResult`
  - `AgentConfig`

Why:

- These are the stable contracts between parser, engine, executor, and PTY wrapper.
- Defining them up front keeps later modules simple and explicit.

### 4. Add agent configuration lookup

Files:

- `src/myteam/workflow/agent_registry.py`

Changes:

- Add a built-in default `codex` agent configuration.
- Add a lookup function for workflow-authored `agent` names.

Why:

- The backlog design treats agent resolution as a separate concern.
- Keeping executable details out of the executor will make later agent additions much simpler.

### 5. Add workflow parsing and validation

Files:

- `src/myteam/workflow/parser.py`

Changes:

- Load YAML from a resolved workflow path.
- Validate the top-level workflow shape.
- Validate each step's required and optional keys.
- Validate identifier-style step names and relevant authored nested keys.
- Validate that authored agent names are known.
- Preserve authored step order.

Why:

- Public workflow-file validation rules should be enforced before execution begins.
- Parser failures should be distinct from runtime failures.

### 6. Add isolated reference resolution

Files:

- `src/myteam/workflow/reference_resolver.py`

Changes:

- Implement exact-string reference substitution for structured `input` data.
- Support `$step.key.path` references and `$$` escaping.
- Reject missing paths and unsupported traversal cases.

Why:

- Reference handling is precise enough to deserve its own module and its own unit tests.
- This keeps reference syntax from leaking into the parser or executor.

### 7. Add the PTY wrapper boundary

Files:

- `src/myteam/workflow/tty_wrapper.py`

Changes:

- Define a generic PTY-backed subprocess runner with inactivity timeout and graceful shutdown support.
- Return a result object with transcript and child exit status.

Why:

- PTY control is the most operationally complex part of the feature.
- Keeping it separate avoids contaminating the rest of the runtime with terminal-management details.

### Refactor completion criteria

At the end of the framework-refactor phase:

- The new workflow support modules exist with stable boundaries.
- Existing disclosure and roster behavior has been moved into thematic packages without changing CLI behavior.
- Existing non-workflow commands behave exactly as before.
- Existing tests should still pass without changing their assertions.

## Feature Addition

This phase uses the refactored framework to add the actual `myteam start` feature.

### 1. Add workflow execution modules

Files:

- `src/myteam/workflow/step_executor.py`
- `src/myteam/workflow/engine.py`

Changes:

- `step_executor.py`
  - Resolve a step's `input` using prior completed step state.
  - Build the canonical agent prompt from authored `input`, `prompt`, and `output`.
  - Run the configured agent through the PTY wrapper.
  - Detect the final completion payload in streamed output.
  - Validate the returned output against the authored `output` template.
  - Return a `StepResult` with full transcript.
- `engine.py`
  - Execute steps in authored order.
  - Maintain prior completed step state.
  - Stop at the first failing step.
  - Return a `WorkflowRunResult` naming the failing step when applicable.

Why:

- This keeps orchestration logic and step-specific runtime behavior separate.
- The engine can stay deterministic and small.

### 2. Add the public `start` command

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

### 3. Support verbose execution output

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

### 4. Add tests that match the documented interface

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

### 5. Update docs surfaced to users

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

### Step state shape for references

Completed step state should be stored under the authored step name in a structure that exposes:

- `prompt`
- `input`
- `agent`
- `output`

This matches the backlog design and keeps reference behavior explicit and predictable.

### Output-template validation

Validation should be structural only:

- nested mappings in the template require nested mappings and required keys in the returned value
- leaf template values are descriptive only and do not constrain runtime scalar type

This keeps the public file format simple and aligned with the documented example.

### Error handling

The public command should distinguish at least these user-visible failure classes:

- workflow file not found
- workflow parse/validation error
- reference resolution error
- step execution failure

All of them should produce a clear stderr message and a non-zero exit code.

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
