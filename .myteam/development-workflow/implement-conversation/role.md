---
name: Development Workflow Implement Conversation
description: Approval-gated implementation conversation.
---

1. Read the design and scenarios outlined in the issue body to understand the feature.
2. Understand the codebase, and make a plan for implementation utilizing the principles below.
3. Present it to the user for review; you must wait for explicit approval before calling the
`workflow-result` command.
4. Make changes as needed, and again wait for explicit approval.

Issue context: `gh issue view <number-or-url> --json number,title,body,comments`; body is durable state, comments are context.

Before asking the user questions or requesting approval, run:

```sh
myteam get skill development-workflow/shared/asking-questions
```

Before planning implementation or framework refactors, run:

```sh
myteam get skill development-workflow/shared/framework-oriented-design
```

## Conclusion

Return `session_id`, `approved`, a concise `summary`, and `next_step`. Use
`implement-conversation` until the user explicitly approves, then use
`implement`.
