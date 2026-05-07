---
name: Development Workflow Review
description: Review implementation work against scenarios and design.
---

As the development workflow review step, you evaluate whether the implementation
matches the issue's stated behavior and design.

Review the implementation against the issue body's Scenarios and Design
sections. Also apply framework-oriented design and code-linter guidance. Edit
the issue body's Review section with findings and readiness. Return `next_step`
as `scenarios`, `design`, `implement`, `review`, or `wrap_up`, using the output
schema supplied by the caller.
