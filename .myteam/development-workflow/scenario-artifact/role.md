---
name: Development Workflow Scenario Artifact
description: Persist approved workflow scenarios.
---

Write or update scenario documentation and summarize or link it in the
issue body's `Scenarios` section. Do not implement code, only scenario 
markdown files.

Return `next_step` as `implement-conversation` when sufficient,
`scenario_conversation` for more scenario work, or
`high_level_design_conversation` when the design is inadequate.
