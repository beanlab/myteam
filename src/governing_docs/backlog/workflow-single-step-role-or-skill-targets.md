# Workflow Single-Step Role Or Skill Targets

## Summary

`myteam` workflows currently execute steps by targeting workflow agents from the workflow agent
registry. That is a good fit for multi-step orchestration, but it is heavier than necessary for a
common case: "run this one role" or "run this one skill" as a workflow step.

The system should support a single-step workflow that targets a role or skill directly without
requiring the author to model that target as a separate workflow agent first.

## Problem

Today a workflow step can choose an `agent`, but that agent namespace is separate from the existing
role and skill model.

This creates friction for simple workflow authoring:

- a user may already have the right instructions captured in a role or skill
- the workflow author still has to think in terms of workflow-agent configuration
- a one-step workflow becomes more ceremony-heavy than the underlying task warrants

That makes workflows less useful as a unifying interface for "run this predefined agent behavior."

## Goals

- Allow a workflow to target an existing role or skill directly for simple cases.
- Reduce authoring ceremony for single-step workflows.
- Preserve a clean conceptual boundary between workflow orchestration and reusable instructions.
- Keep the authored interface explicit enough that readers can tell what kind of target a step uses.

## Proposed Change

Extend the workflow format so a step can target a role or skill directly, rather than only a named
workflow agent.

Possible authored shapes include:

- a dedicated `role:` field
- a dedicated `skill:` field
- a more general `target:` field with an explicit target kind

The preferred design should make these cases easy to read:

- "run the `developer` role as this step"
- "run the `python/testing` skill as this step"

For the specific use case in this item, a one-step workflow should be able to invoke one such target
cleanly, without forcing the author through extra workflow-agent registry setup.

The design should also define:

- how the role or skill instructions are loaded into the launched agent session
- whether role/skill-targeted steps still use the normal workflow completion contract
- how this interacts with the existing default workflow agent runtime
- what validation errors should look like when the referenced role or skill does not exist

## Scope Boundaries

- This item is about workflow targeting semantics, not broader workflow scheduling changes.
- This does not require replacing the existing workflow agent registry for more complex cases.
- This does not yet require multi-target steps or dynamic target selection.

## Open Questions

- Should role and skill targeting be limited to single-step workflows at first, or allowed in any
  workflow step immediately?
- Is a dedicated `role:` / `skill:` syntax clearer than a generic `target:` abstraction?
- Should a role/skill-targeted step still run through the same PTY-backed workflow agent runtime, or
  does it need a distinct execution path?
- How should role and skill loading interact with step `input` and `output` contracts?
