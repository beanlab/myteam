# Workflow Improvements

This document captures the main ways `myteam workflows` can grow while staying faithful to the
existing `myteam` architecture and remaining easy for users to adopt.

## Guiding Principle

Workflows should feel like a natural extension of `myteam`'s role-and-skill system, not like a
separate orchestration product. The best improvements are the ones that preserve these ideas:

- local, file-based configuration
- role-driven behavior
- deterministic handoff between steps through structured outputs
- simple commands that hide AppServer details

## Improvements

### 1. Make workflows first-class `myteam` objects

Right now the workflow runner is driven by a YAML path. A stronger `myteam` fit would be to support
workflow discovery under a conventional location such as `.myteam/workflows/`.

This would enable commands such as:

```bash
myteam workflows start poetry
```

instead of always requiring:

```bash
myteam workflows start .myteam/workflows/poetry.yaml
```

This matches how `myteam` already treats roles and skills as named local assets.

### 2. Add `myteam new workflow <name>`

Workflows are much easier to adopt if the CLI scaffolds them. A `new workflow` command could create:

- a starter YAML file using the `template.yaml` shape
- example `inputs` and `outputs`
- example `{from: previous_step.output}` references
- small inline comments describing deterministic workflow expectations

This would reduce friction and keep users inside established `myteam` conventions.

### 3. Support workflow-level inputs

Workflows will be more reusable if shared values can be declared once at the top level and reused by
many steps.

Example:

```yaml
inputs:
  theme: autumn rain
  audience: children

draft:
  role: free_verse
  inputs:
    theme:
      from: input.theme
  outputs:
    poem: first draft
```

This improves usability without weakening determinism.

### 4. Let roles define optional default output contracts

Today the workflow file owns the output contract. That is fine for v1, but it creates duplication
when the same role is used across many workflows.

A future improvement would let a role publish optional workflow metadata such as:

- default output fields
- expected output types
- preferred input names

The workflow could still override these, but the role would provide a stronger reusable contract.

### 5. Improve interactive step controls

The current `/done` interaction is useful, but the experience can be clearer and easier to learn.

Useful additions:

- `/help` to show available workflow commands
- `/status` to show current step, thread, turn, and token usage so far
- `/outputs` to preview finalized outputs from completed steps
- `/retry` to restart the current step attempt cleanly
- `/cancel` to stop the workflow without deleting state

These commands would make workflows feel more approachable while keeping the underlying execution
model deterministic.

### 6. Make conversation mode and finalization mode explicit

The runner now supports multi-turn step conversations followed by `/done`. That is the right shape,
but the UI can explain it more clearly.

The terminal should make it obvious when a step is:

- accepting conversational guidance
- being finalized into structured output
- completed and ready to hand off data to the next step

This reduces confusion, especially for users who want to collaborate with a role before locking in
its final outputs.

### 7. Expand `workflows status`

`status` is much more valuable if it becomes the user's main debugging and resumption surface.

It should eventually show:

- current workflow state
- current or next step
- completed steps
- finalized outputs from completed steps
- per-step token usage
- last failure reason
- whether the workflow is waiting for user interaction

This keeps workflow state transparent without exposing AppServer protocol details.

### 8. Preserve role ownership and use workflows only for orchestration

`myteam` works best when roles remain the source of behavior and workflows remain the source of
sequence and data flow.

That means:

- roles define how work is done
- workflows define when roles run
- structured outputs define what moves between roles

Keeping that boundary clear will help the architecture stay understandable as workflows grow.

### 9. Support explicit interactive and non-interactive modes

Some users will want to collaborate at each step. Others will want the workflow to run straight
through.

Helpful options would be:

- `myteam workflows start <name> --interactive`
- `myteam workflows start <name> --no-input`

This gives users more control while preserving the same deterministic state model.

### 10. Add workflow authoring guidance as a `myteam` skill

As workflows become more central, authoring them should become easier to learn. A dedicated skill
could document:

- workflow design conventions
- how to choose outputs that are stable and easy to validate
- when to chain steps versus share root inputs
- how to structure roles for workflow reuse

That keeps workflow knowledge inside the same `myteam` ecosystem as the rest of the project.

## Priority Summary

If we want the highest-impact improvements first, the best next investments are:

1. workflow discovery by name under `.myteam/workflows/`
2. `myteam new workflow <name>`
3. workflow-level inputs
4. better interactive commands and step help
5. richer `myteam workflows status`
