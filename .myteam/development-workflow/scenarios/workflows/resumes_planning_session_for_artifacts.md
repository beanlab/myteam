# Resumes Planning Session For Artifacts

## Purpose

Reuse approved planning context.

---

# Context

A development workflow has completed an approval-gated planning conversation
step. The conversation result includes the session ID of the agent session that
held the approved conversation.

The workflow is ready to run the paired artifact-writing step for the same
planning phase.

---

# Action

The workflow starts the artifact-writing step.

---

# Outcome

The workflow invokes the agent runner with the session ID returned by the
paired conversation step.

The artifact-writing step resumes the same agent session instead of starting a
fresh planning conversation, receives the phase-specific artifact-writing
instructions, and can use the approved conversation context when writing its
durable artifact.

If the artifact-writing step cannot produce a valid artifact from the approved
context, it reports a next step that returns to an allowed conversation phase
instead of inventing missing approval.

---

# Related Scenarios

- scenarios/workflows/gates_planning_conversations_on_approval.md
- scenarios/workflows/records_staged_planning_artifacts.md
