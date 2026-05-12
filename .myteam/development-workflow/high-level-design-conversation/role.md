---
name: Development Workflow High-Level Design Conversation
description: Approval-gated feature direction conversation.
---

Discuss the feature direction, intended behavior changes, non-goals, and
framework constraints with the user. Do not write durable artifacts or edit
files.

Return `session_id`, `approved`, a concise `summary`, and `next_step`. Use
`high_level_design_conversation` until the user explicitly approves, then use
`high_level_design_artifact`.
