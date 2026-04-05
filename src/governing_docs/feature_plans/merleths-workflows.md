# Feature Plan: Deterministic Workflow Runner

## Pipeline Status

- [x] Create the git branch
- [x] Plan the feature
- [x] Update the interface document
- [x] Refactor the framework
- [x] Update the test suite
- [x] Implement the feature
- [ ] Conclude the feature

## Goal

Add a deterministic workflow runner to `myteam` that can execute a simple YAML workflow through
role-based Codex AppServer threads while preserving structured step outputs and allowing live
communication with the currently running step.

Extend that runner so workflows feel like a native `myteam` asset instead of a path-only advanced
feature.

## Framework Refactor

Introduce reusable support code so workflow execution fits the existing CLI cleanly instead of
hard-coding behavior in one command function.

Planned refactors:

1. Extract loader execution into a shared helper that can either stream or capture role/skill loader
   output.
2. Add a workflow runner module responsible for:
   - loading and validating workflow YAML
   - persisting run state under `.myteam/workflow_runs/`
   - talking to a line-delimited JSON-RPC AppServer subprocess
   - handling multi-turn step conversations and resumable failures
3. Keep the CLI wiring thin by exposing `workflows start`, `workflows resume`, and
   `workflows status` through `src/myteam/cli.py`.
4. Keep the workflow coordinator thin by separating:
   - workflow-definition loading and validation
   - workflow run-state persistence and token accounting
   - AppServer JSON-RPC process transport
   - console interaction for the active step
5. Integrate workflow creation and lookup into the existing command framework by:
   - adding `myteam new workflow <name>`
   - resolving `.myteam/workflows/<name>.yaml` from `myteam workflows start <name>`
   - preserving the existing explicit path-based `workflows start` behavior

The existing role/skill loading behavior should remain unchanged after this refactor.

## Feature Addition

Implement the first workflow format using the `template.yaml` shape:

- top-level ordered step names
- per-step `role`
- per-step `inputs`
- per-step `outputs`

Behavior details:

1. `myteam workflows start <path>` runs steps strictly in order.
2. Each step loads the declared role instructions, creates a fresh AppServer thread, and starts one
   turn.
3. The active step streams live output and can accept additional user follow-up turns on the same thread before finalization.
4. In interactive use, the user types `/done` to finalize the current step and advance.
5. A step is only complete when the final assistant message is valid JSON and its keys exactly match
   the declared `outputs`.
6. Completed step outputs are stored and may be referenced by later steps using
   `{from: prior_step.output}`.
7. Failed runs can be resumed from the first incomplete step with `myteam workflows resume <run_id>`.
8. `myteam new workflow <name>` scaffolds `.myteam/workflows/<name>.yaml` from `planning_files/template.yaml`.
9. `myteam workflows start <name>` resolves the named workflow from `.myteam/workflows/`, while
   still accepting explicit filesystem paths.
10. Name-based workflow lookup should prefer the native `.myteam/workflows/` location and keep the
    resolution rules simple and predictable.

## Test Plan

Add high-level CLI tests that prove:

- ordered workflow execution succeeds and persists outputs
- step conversation works on the same thread before finalization
- failed runs can be resumed without rerunning already successful steps
- workflow status can be read from disk after a run completes or fails
- `myteam new workflow <name>` scaffolds the expected file in `.myteam/workflows/`
- `myteam workflows start <name>` resolves a named workflow from `.myteam/workflows/`
- explicit path-based workflow startup still works
