---
name: Development Workflow Issue State
description: |
  Local development-workflow guidance for using GitHub issue bodies as
  workflow state. Load this skill before selecting a workflow start step or
  editing workflow sections in an issue body.
---

# Workflow Issue State

The development workflow stores durable workflow state in the GitHub issue body.

## Required Sections

Each selected or created issue must contain these sections:

- `Details`
- `Out-of-scope`
- `Dependencies`
- `Scenarios`
- `Design`
- `Implementation`
- `Review`
- `Wrap Up`
- `Pull Request`

Add any missing section with `TBD.` as placeholder content. Preserve existing
content when normalizing older issues.

## Durable Source

- Treat the issue body as the source of durable requirements and workflow state.
- Treat comments as discussion, clarifications, implementation notes, and later
  context that may need to be folded into the body when relevant.
- Do not use the issue body as an exhaustive implementation plan unless a later
  workflow step has approved and recorded that plan.

## Start Step Selection

For a new item, return `start_step` as `design-conversation`.

For an existing item, choose the earliest step that still needs meaningful work:

- `design-conversation` when desired behavior, constraints, or non-goals are not
  sufficiently understood or approved.
- `scenario_conversation` when design direction is sufficient but observable
  scenarios are missing or need approval.
- `implement-conversation` when design and scenarios are sufficient but the
  implementation plan needs user approval.
- `implement` when the implementation plan is approved but code work remains.
- `review` when scenarios, design, and implementation context are sufficient and
  the next useful action is review.

Do not return `wrap_up` as the starting step. If the user explicitly asks to
resume at a later allowed step, honor that request when the issue has enough
context for the later step.

## Backlog Step Output

Return the issue identifiers and a concise backlog summary using the output
schema supplied by the caller. Include:

- `issue_number`
- `issue_id`
- `project_item_id`
- `backlog_summary`
- `start_step`
