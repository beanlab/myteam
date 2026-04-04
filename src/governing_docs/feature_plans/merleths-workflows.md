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

## Test Plan

Add high-level CLI tests that prove:

- ordered workflow execution succeeds and persists outputs
- step conversation works on the same thread before finalization
- failed runs can be resumed without rerunning already successful steps
- workflow status can be read from disk after a run completes or fails
