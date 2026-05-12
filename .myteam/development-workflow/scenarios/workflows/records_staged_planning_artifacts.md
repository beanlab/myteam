# Records Staged Planning Artifacts

## Purpose

Persist approved planning results.

---

# Context

A development workflow is running an artifact-writing step after its paired
planning conversation step has been explicitly approved.

The tracked issue contains these sections:

- Design
- Scenarios
- Implementation

---

# Action

The artifact-writing step completes successfully.

---

# Interaction

| Action | Outcome |
| --- | --- |
| High-level design artifact step | Updates the issue's `Design` section with the approved feature direction and framework-level decisions. |
| Scenario artifact step | Writes or updates scenario documentation and records repository-relative links or summaries in the issue's `Scenarios` section. |
| Implementation plan artifact step | Updates the issue's `Implementation` section with the approved implementation plan. |

---

# Outcome

Each artifact-writing step persists only the durable artifact owned by its
planning phase. Later implementation work may append code-change and test
results to the issue's `Implementation` section, but the planning artifact
steps do not perform implementation or review work.

---

# Related Scenarios

- scenarios/workflows/resumes_planning_session_for_artifacts.md
- scenarios/workflows/restricts_planning_phase_routing.md
