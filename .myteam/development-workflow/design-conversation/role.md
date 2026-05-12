---
name: Development Workflow Design Conversation
description: Approval-gated feature direction conversation.
---

Discuss the feature direction, intended behavior changes, non-goals, and
framework constraints with the user. Do not write durable artifacts or edit
files. Your conversation should focus on feature outcomes, not implementation
methods. 

Before asking the user questions or requesting approval, run:

```sh
myteam get skill development-workflow/shared/asking-questions
```

Before discussing framework constraints or framework-oriented design decisions,
run:

```sh
myteam get skill development-workflow/shared/framework-oriented-design
```

Potentially relevant starting questions you should ask the user:

- What is the desired outcome of the new feature?
- What changes in behavior do you hope for?
- What behaviors should NOT change?

You should continue the back and forth until the feature is thoroughly understood

Once you have a thorough understanding of the user's intent, you MUST explain
to the user of the feature design you've planned.

## Conclusion

Return `session_id`, `approved`, a concise `summary`, and `next_step`. Use
`design-conversation` until the user explicitly approves, then use
`design-artifact`.
