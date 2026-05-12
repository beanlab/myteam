---
name: Development Workflow Scenario Conversation
description: Approval-gated scenario planning conversation.
---

1. Review the feature design in the issue body. 
2. Run `myteam get skill development-workflow/shared/scenario-documentation`
to load local instructions for authoring scenarios.
3. Before asking the user questions or requesting approval, run
`myteam get skill development-workflow/shared/asking-questions`.
4. Present your proposed scenario(s) to the user for review and wait for 
explicit approval before calling the `workflow-result` command.
5. Make changes as needed until explicit approval is given.
6. Return `session_id`, `approved`, a concise `summary`, and `next_step`. Use
`scenario_conversation` until the user explicitly approves, then use
`scenario_artifact`.
