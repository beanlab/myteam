---
name: Development Workflow Implement
description: Implement a designed workflow issue and record test results.
---

As the development workflow implementation step, you make the code changes for
the feature described by the issue.

Implement the feature according to the issue body's Scenarios and Design
sections. Run relevant tests. Edit the issue body's Implementation section with
the changes and test results. Return `next_step` as `scenarios`, `design`,
`implement`, or `review`, using the output schema supplied by the caller.
