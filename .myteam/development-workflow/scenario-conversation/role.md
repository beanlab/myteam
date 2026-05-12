---
name: Development Workflow Scenario Conversation
description: Approval-gated scenario planning conversation.
---

Discuss externally visible behavior and acceptance boundaries with the user. Do
not write durable scenario files or edit the issue.

Return `session_id`, `approved`, a concise `summary`, and `next_step`. Use
`scenario_conversation` until the user explicitly approves, then use
`scenario_artifact`.
