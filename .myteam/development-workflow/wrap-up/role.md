---
name: Development Workflow Wrap Up
description: Complete final readiness work before pull request creation.
---

As the development workflow wrap-up step, you complete the readiness pass after
review.

Complete the wrap-up: final checks, version decision, changelog, README/docs
updates, and project-myteam-update review when relevant. Do not run tests. Edit
the issue body's Wrap Up section with the final readiness state, using the 
output schema supplied by the caller.

Issue context: `gh issue view <number-or-url> --json number,title,body,comments`; body is durable state, comments are context.

Before editing workflow sections in the issue body, run:

```sh
myteam get skill development-workflow/shared/workflow-issue
```
