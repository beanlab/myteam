---
name: Development Workflow Implement Conversation
description: Approval-gated implementation conversation.
---

1. Read the design and scenarios outlined in the issue body to understand the feature.
2. Understand the codebase, and make a plan for implementation utilizing the principles below.
3. Present it to the user for review; you must wait for explicit approval before calling the
`workflow-result` command.
4. Make changes as needed, and again wait for explicit approval.

## Feature Implementation - Framework Oriented Design

### Philosophy

An application is a combination of framework and business logic.

We seek to separate framework code for business logic code.

*Framework* refers to the internal, helper code that supports the primary API of the application,
as well as the conventions and patterns used in the codebase to create consistency and structure.

When preparing to implement a feature, understand the existing framework:

- Why was the code written the way it does? What problems does the current design solve?
- What helper functions exist? Why do they exist?

Then consider: should changes be made to the framework to support the new feature?

The business logic of the new feature should fit cleanly within the framework.
Therefore, a change to the framework may be needed first, 
followed by a change to the business logic.

If a change to the framework is needed, refactor the code accordingly without adding
any new behavior. 

Guidance:

- Review the principles of self-documenting code and follow them.
- Functions should be simple, focused, and easy to read.
- When creating helper functions, look for existing behavior.

## Conclusion

Return `session_id`, `approved`, a concise `summary`, and `next_step`. Use
`implement-conversation` until the user explicitly approves, then use
`implement`.
