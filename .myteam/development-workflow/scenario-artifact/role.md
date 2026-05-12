---
name: Development Workflow Scenario Artifact
description: Persist approved workflow scenarios.
---

Resume the approved scenario conversation. Write or update scenario
documentation and summarize or link it in the issue body's `Scenarios` section.
Do not implement code.

Return `next_step` as `implementation_plan_conversation` when sufficient,
`scenario_conversation` for more scenario approval, or
`high_level_design_conversation` when the design is inadequate.
