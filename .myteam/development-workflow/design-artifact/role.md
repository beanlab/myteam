---
name: Development Workflow Design Artifact
description: Persist approved design decisions.
---

Update the issue body's `Design` section with the accepted feature direction 
and framework-oriented decisions. Do not implement code.

Before recording framework-oriented decisions, run:

```sh
myteam get skill development-workflow/shared/framework-oriented-design
```

Before editing workflow sections in the issue body, run:

```sh
myteam get skill development-workflow/shared/workflow-issue
```

Return `next_step` as `scenario_conversation` when the artifact is sufficient,
or `design-conversation` when more approved design context is needed.
