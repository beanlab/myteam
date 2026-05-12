---
name: Development Workflow Scenario Conversation
description: Approval-gated scenario planning conversation.
---

1. Review the feature design in the issue body. 
2. Run `myteam get skill documentation` to load instructions for authoring
scenarios.
3. Present your proposed scenario(s) to the user for review and wait for 
explicit approval before calling the `workflows-result` command.
4. Make changes as needed until explicit approval is given.
5. Return `session_id`, `approved`, a concise `summary`, and `next_step`. Use
`scenario_conversation` until the user explicitly approves, then use
`scenario_artifact`.
