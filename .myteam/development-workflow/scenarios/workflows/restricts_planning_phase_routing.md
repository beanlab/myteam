# Restricts Planning Phase Routing

## Purpose

Limit workflow jumps between planning phases.

---

# Context

A staged development workflow is running before implementation work begins. Its
planning sequence contains these steps:

1. high-level design conversation
2. high-level design artifact
3. scenario conversation
4. scenario artifact
5. implementation plan conversation
6. implementation plan artifact

---

# Action

A planning step reports its next workflow step.

---

# Outcome

Conversation steps may repeat themselves until explicit approval is recorded,
then advance only to their paired artifact-writing step.

Artifact-writing steps may advance to the next planning phase when the approved
artifact is sufficient. They may return to their paired conversation step when
the approved context is insufficient for the artifact.

The scenario artifact step may return to high-level design conversation when
the design is inadequate for scenario writing. The implementation plan artifact
step may return to scenario conversation when the scenarios are inadequate for
implementation planning.

Unsupported jumps outside these phase boundaries are rejected instead of being
accepted as valid workflow routing.

---

# Related Scenarios

- scenarios/workflows/gates_planning_conversations_on_approval.md
- scenarios/workflows/records_staged_planning_artifacts.md
