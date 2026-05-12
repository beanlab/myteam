# Runs Development Workflow From Backlog To Completion

## Purpose

Define the externally visible development workflow from issue selection through
completion handoff.

---

# Context

A user starts the development workflow with a feature request, or resumes an
existing backlog issue. The workflow owns issue preparation, staged planning,
implementation, review, wrap-up, and completion handoff.

The tracked issue contains these durable sections:

- Details
- Out-of-scope
- Dependencies
- Scenarios
- Design
- Implementation
- Review
- Wrap Up
- Pull Request

---

# Action

The workflow runs the issue from backlog selection through the planning,
implementation, review, wrap-up, and completion steps.

---

# Interaction

| Step | Outcome |
| --- | --- |
| Backlog | Selects or creates an issue with the required sections and chooses the starting workflow step. |
| High-level design conversation | Discusses feature direction with the user until explicit approval is recorded, returning the conversation `session_id`. |
| High-level design artifact | Resumes the approved high-level design session and records the accepted design in the issue. |
| Scenario conversation | Discusses externally visible behavior and acceptance boundaries until explicit approval is recorded, returning the conversation `session_id`. |
| Scenario artifact | Resumes the approved scenario session, writes scenario documentation, and records scenario links or summaries in the issue. |
| Implementation plan conversation | Discusses implementation sequence, risks, and validation until explicit approval is recorded, returning the conversation `session_id`. |
| Implementation plan artifact | Resumes the approved implementation planning session and records the implementation plan in the issue. |
| Implementation | Makes code changes, records implementation work and test results in the issue, and sends the work to review. |
| Review | Records review findings and either routes back to the needed workflow phase or allows wrap-up. |
| Wrap Up | Performs final issue and project cleanup after review approval. |
| Complete | Creates or records the pull request and moves the project item to waiting for review. |

---

# Outcome

The workflow reaches completion only after the issue has moved through staged
planning, implementation, review, and wrap-up. Each planning artifact step uses
the session ID from its paired approved conversation. If a step cannot proceed
with the available context, it returns to an allowed earlier workflow phase
instead of skipping required approval or artifact work.

---

# Related Scenarios

- scenarios/workflows/gates_planning_conversations_on_approval.md
- scenarios/workflows/resumes_planning_session_for_artifacts.md
- scenarios/workflows/records_staged_planning_artifacts.md
- scenarios/workflows/restricts_planning_phase_routing.md
