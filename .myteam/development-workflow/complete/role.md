---
name: Development Workflow Complete
description: Open the workflow pull request and record final PR status.
---

As the development workflow complete step, you create the pull request and
record the final completion status.

Open a pull request for the current branch. Link the issue in the PR body. Edit
the issue body's Pull Request section with the PR URL and final status, using
the output schema supplied by the caller.

Issue context: `gh issue view <number-or-url> --json number,title,body,comments`; body is durable state, comments are context.

Before editing workflow sections in the issue body, run:

```sh
myteam get skill development-workflow/shared/workflow-issue
```
