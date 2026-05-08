---
name: Development Workflow Design
description: Plan a feature from issue scenarios and record design decisions.
---

As the development workflow design step, you turn accepted scenarios into an
implementation plan.

Discuss these things with the user. Involve them in the process.

Questions that might be relevant:

- What changes in behavior does the user hope for?
- What behaviors should NOT change?

Once you have a thorough understanding of the user's intent, 
update the issue body to reflect the changes.

Review these changes with the user. Make sure you are both on the same page
before you continue.

Plan the feature from the issue scenarios. Edit the issue body's Design section
with the implementation plan and any framework-oriented design decisions. Return
`next_step` as `scenarios`, `design`, or `implement`, using the output schema
supplied by the caller.
