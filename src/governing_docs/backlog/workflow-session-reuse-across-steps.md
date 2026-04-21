# Workflow Session Reuse Across Steps

## Summary

`myteam` workflows currently treat each step as a fresh session. That keeps execution isolated and
simple, but it also throws away useful conversational and working context between related steps.

We want to support a mode where a later step can reuse the session from an earlier step. In that
model, once step 1 reaches its completion objective, step 2 can inject new input into that same
session and continue from the existing context instead of starting over.

## Problem

Fresh-session execution is not always the best fit for sequential work performed by the same agent.

Some workflows are naturally continuous:

- step 1 gathers context or produces an initial artifact
- step 2 refines, extends, or transforms that work
- the same agent context would be valuable across both steps

Today, that continuity has to be approximated indirectly through structured output and fresh prompts.
That is valuable, but it is not equivalent to continuing the same live session.

This creates several limitations:

- useful conversational and tool-use context is discarded between steps
- later steps may need to restate information the session already knows
- workflows cannot model "finish this objective, then continue in place with this new instruction"
- the runtime has no explicit concept of a completed-but-reusable session

## Goals

- Allow selected workflow steps to continue an earlier session instead of launching a new one.
- Keep the normal completion boundary intact: step 1 must still satisfy its objective before step 2
  can continue the session.
- Preserve the structured workflow model while enabling session continuity where it is beneficial.
- Make session reuse explicit in authored workflow semantics rather than implicit runtime magic.

## Proposed Change

Extend the workflow execution model to support step-to-step session reuse.

At a high level:

1. a step runs normally and reaches a valid completion state
2. instead of always terminating that session permanently, the runtime can retain it as reusable
   session state
3. a later step explicitly declares that it continues from that prior session
4. the runtime injects the later step's new input/objective into the retained session
5. the continued session works toward the new step's completion contract

This should remain step-oriented from the workflow author's perspective. Even when two steps share a
session, they should still be distinct workflow steps with their own:

- authored prompt
- optional input
- expected output contract
- success or failure outcome

The design likely needs explicit answers for:

- how a step declares that it continues a prior session
- whether only the immediately previous step can be reused, or any named earlier step
- how long reusable sessions stay alive
- what lifecycle event converts a live step session into a reusable continuation point

## Scope Boundaries

- This item is about controlled reuse of completed step sessions, not arbitrary concurrent session
  sharing.
- This does not require abandoning isolated fresh-session execution as the default.
- This does not yet require durable persistence of reusable sessions across process restarts.
- This is not the same feature as suspended parent/child delegation, though the runtime machinery may
  overlap.

## Open Questions

- What authored syntax best expresses continuation: `continue_from: step1`, a session identifier, or
  something else?
- Should reused sessions be limited to steps that use the same agent/runtime configuration?
- How should transcripts be represented when multiple workflow steps share one underlying session?
- If a reused session drifts or fails after the first step completed successfully, how should that be
  surfaced in workflow results?
- Does the current PTY wrapper need a persistent session abstraction to support this cleanly?
