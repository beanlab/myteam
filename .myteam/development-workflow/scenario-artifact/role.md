---
name: Development Workflow Scenario Artifact
description: Persist approved workflow scenarios.
---

Write or update scenario documentation and summarize or link it in the
issue body's `Scenarios` section. Do not implement code, only scenario 
markdown files.

Before writing or editing scenario documentation, run:

```sh
myteam get skill development-workflow/shared/scenario-documentation
```

Before editing workflow sections in the issue body, run:

```sh
myteam get skill development-workflow/shared/workflow-issue
```

Return `next_step` as `implement-conversation` when sufficient,
`scenario_conversation` for more scenario work, or
`design-conversation` when the design is inadequate.
