---
name: Development Workflow High-Level Design Artifact
description: Persist approved high-level design decisions.
---

Resume the approved high-level design conversation. Update the issue body's
`Design` section with the accepted feature direction and framework-oriented
decisions. Do not implement code.

Return `next_step` as `scenario_conversation` when the artifact is sufficient,
or `high_level_design_conversation` when more approved design context is needed.
