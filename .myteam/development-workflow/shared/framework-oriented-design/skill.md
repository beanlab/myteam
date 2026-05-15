---
name: Development Workflow Framework-oriented Design
description: |
  Local development-workflow guidance for framework-oriented design.
  Load this skill when designing, planning, implementing, or reviewing code
  changes in the development workflow.
---

# Framework-oriented Design

An application is a combination of framework and business logic.

Seek to separate framework code from business logic code.

*Framework* refers to the internal helper code that supports the primary API of
the application, as well as the conventions and patterns used in the codebase to
create consistency and structure.

When preparing to implement a feature, understand the existing framework:

- Why was the code written the way it is?
- What problems does the current design solve?
- What helper functions exist?
- Why do those helpers exist?

Then decide whether the framework should change to support the new feature.

The business logic of the new feature should fit cleanly within the framework.
When a framework change is needed, make the behavior-neutral refactor first,
then add or adjust the business logic.

Guidance:

- Prefer self-documenting code.
- Keep functions simple, focused, and easy to read.
- Before creating a helper, look for existing behavior that can be reused or
  reasonably generalized.
- Avoid conceptual duplication, even when the code is not exact copy-paste.
- Use names that explain the domain concept or framework responsibility.
- Decompose large functions, modules, or packages when doing so clarifies the
  existing framework or the new behavior.
