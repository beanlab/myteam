# Suspended Parent Delegation

## Summary

`myteam` workflows currently fit a step-at-a-time execution model where the orchestrator runs one
step, waits for completion, and then proceeds. Separately, many agent systems use a spawn-and-poll
delegation model where a parent session continues to exist while periodically checking on a child.

We want a different delegation mode for some cases: complete suspension of the parent session while a
delegated child session runs, followed by resumption of the original parent session with the child's
result injected back into it.

This should build on the step execution framework rather than being treated as an unrelated
mechanism.

## Problem

Spawn-and-poll delegation is not always the right execution shape.

For some workflows, the intended control flow is:

1. the current agent reaches a point where it wants to delegate
2. the parent session is suspended, not left active and polling
3. a second agent session runs to completion
4. the parent's session is resumed with the delegated result available in context

The current workflow runtime does not model this kind of in-band delegation directly.

That creates several limitations:

- delegation behavior lives outside the main step execution framework
- parent and child execution lifecycles are not modeled as one coherent control-flow system
- it is harder to reason about transcript boundaries, timeout behavior, and result handoff
- the user experience differs from the simpler "pause here, do that, resume here" mental model

## Goals

- Support a delegation mode that suspends the parent session completely while a child session runs.
- Reuse the step execution framework where possible instead of inventing a separate orchestration
  stack.
- Make parent suspension and resume explicit in the execution model.
- Provide a clear mechanism for handing the child result back into the resumed parent session.
- Preserve debuggability around transcripts, failure states, and lifecycle events.

## Proposed Change

Design a delegation tool or runtime capability that can be invoked from within an executing workflow
session and that links back into the parent `myteam start` process.

At a high level, the behavior should be:

1. the parent agent requests delegated execution
2. the workflow runtime suspends the current parent PTY session in a controlled way
3. the runtime launches a child session using the step execution framework
4. the child session runs to completion or failure
5. the runtime resumes the original parent session
6. the runtime injects the child result into the resumed parent session so it can continue

This likely requires explicit runtime concepts for:

- suspended session state
- child-session ownership and lifecycle
- resume payload format
- failure propagation when the child does not complete successfully

The design should also define whether this capability appears as:

- a workflow-level primitive
- a tool callable by agents running inside the workflow runtime
- or a hybrid where the tool is the user-facing surface but the workflow engine owns the mechanics

## Scope Boundaries

- This item is about complete-suspension delegation, not general concurrent multi-agent scheduling.
- This does not require replacing spawn-and-poll delegation everywhere immediately.
- This does not require durable persistence or cross-process recovery on first implementation.
- This is not yet about nested arbitrary delegation trees unless the base model naturally supports
  them.

## Open Questions

- Should the parent session be resumed in the same PTY process, or reconstructed from saved state?
- What exact payload should be injected back into the resumed parent: raw child output, structured
  result, transcript summary, or some combination?
- How should child failure surface to the parent: immediate workflow failure, resumable error, or a
  normal structured result path?
- Does the suspension/resume mechanism belong in `tty_wrapper`, `step_executor`, or a higher-level
  workflow orchestration layer?
- How should timeouts be split between the suspended parent and the active child?
