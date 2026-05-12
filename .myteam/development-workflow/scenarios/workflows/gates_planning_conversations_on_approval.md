# Gates Planning Conversations On Approval

## Purpose

Require explicit approval before artifact work.

---

# Context

A development workflow is running a planning conversation step for one of these
phases:

- high-level design
- scenario design
- implementation planning

The conversation step has access to the issue context and the phase-specific
conversation instructions. It has not been instructed to write durable project
artifacts for that phase.

---

# Action

The planning conversation reaches a point where the user explicitly indicates
approval for the proposed phase result.

---

# Outcome

The conversation step advances to its paired artifact-writing step 
returning the result.

The result includes the agent session ID, an approval value, a concise summary
of the approved result, and the next workflow step.

The conversation step does not write durable scenario files, issue sections, or
implementation plans.

---

# Related Scenarios

- scenarios/workflows/resumes_planning_session_for_artifacts.md
- scenarios/workflows/restricts_planning_phase_routing.md
