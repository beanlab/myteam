---
name: Development Workflow Backlog
description: Select or create the backlog issue for the development workflow.
---

As the development workflow backlog step, you establish the GitHub issue that
will carry the rest of the workflow state.

Before inspecting, selecting, editing, or creating any GitHub issue, ask the
user whether this workflow should use an existing issue or open a new one.

This question is mandatory unless the workflow input already includes one of:

- a non-empty `issue_number`
- a non-empty `issue_id`
- a non-empty `project_item_id`
- a non-empty `feature_request`

If none of those fields are present, stop and wait for the user's answer. Do
not infer the issue from the project backlog.

Ask:

> Are we working on an existing issue, or should I open a new one? If existing,
> provide the issue number or title. If new, describe the feature/request to
> capture.

Run `myteam get skill project-management/backlog`.

## Existing Item

Identify the GitHub issue for this development workflow from the Bean Lab
project, edit the issue body so it contains the required workflow sections
supplied in the input, and return the issue identifiers and a concise
backlog summary using the output schema.

## New Item

First read `application_interface.md` to understand the current design and intent of the project.
Then seek to understand what the user wants to change. 
Is it a new behavior? Modifying an existing behavior? A bugfix?

Create the new issue with an appropriate name.
Edit the issue body so it contains the required workflow sections supplied in the input.


