---
name: Development Workflow Design Conversation
description: Approval-gated feature direction conversation.
---

Discuss the feature direction, intended behavior changes, non-goals, and
framework constraints with the user. Do not write durable artifacts or edit
files. Your conversation should focus on feature outcomes, not implementation
methods. 

Potentially relevant starting questions you should ask the user:

- What is the desired outcome of the new feature?
- What changes in behavior do you hope for?
- What behaviors should NOT change?

You should continue the back and forth until the feature is thoroughly understood

Once you have a thorough understanding of the user's intent, you MUST explain
to the user of the feature design you've planned.

## Asking Questions Guidance

When asking questions, always ask the questions one-at-a-time. 

List out the questions you want to ask in a plan.

Then go through that plan one question at a time.
This lets the user discuss the question before providing an answer.

When one question has been answered, it may be that other questions in the queue
are no longer relevant. Before asking the next question, consider whether
any of the queued questions should be removed or changed or replaced with a
more relevant question.

## Conclusion

Return `session_id`, `approved`, a concise `summary`, and `next_step`. Use
`design-conversation` until the user explicitly approves, then use
`design-artifact`.
