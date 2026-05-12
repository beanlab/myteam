---
name: Development Workflow Implement
description: Persist the approved implementation plan and implement it.
---

Update the issue body's `Implementation` section with the approved
implementation plan and implement it.

Before implementing code or editing the implementation plan, run:

```sh
myteam get skill development-workflow/shared/framework-oriented-design
```

Before editing workflow sections in the issue body, run:

```sh
myteam get skill development-workflow/shared/workflow-issue
```

Return `next_step` as `review` when sufficient,
`implement-conversation` for more implementation approval, `implement` when
more implementation work remains, or
`scenario_conversation` when scenarios are inadequate.
