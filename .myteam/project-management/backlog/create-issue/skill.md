---
name: "Create Github Issue"
description: |
  Load this skill when creating a GitHub project backlog issue or
  drafting an issue title, body, type, or labels.
---

# Create Github Issue

Create project backlog items as GitHub Issues and add them to the
Bean Lab GitHub Project.

## Project Target

Created issues must be added to the Bean Lab GitHub Project:

- Project URL: `https://github.com/orgs/beanlab/projects/13/views/1`
- Project owner: `beanlab`
- Project number: `13`

The token must include the `project` scope. Check with
`gh auth status`; add it with `gh auth refresh -s project` if needed.

## Issue Types and Labels

Every issue must have a GitHub issue type:

- `Bug`
- `Feature`
- `Task`

For labels, add `needs-clarification` only when the input is ambiguous or incomplete

## Title Rules

- Use a short imperative summary.
- Do not write a full sentence.
- Prefer concise, action-oriented phrasing when the issue represents
  work to do.

## Body Template

Use this issue body template:

```md
Created on: <YYYY-MM-DD>
Created by: <user>

## Details

<Overview of the item. Capture the problem, intent, and details
currently known.>

## Out-of-scope

<Changes or features left for other backlog items. Reference related
issues when known.>

## Dependencies

<Other backlog issues this item depends on. Reference related issues
when known.>
```

## Creation Workflow

- Create issues automatically once enough input exists; do not add a
  confirmation step.
- Assign the best-fit GitHub issue type.
- Creating a backlog issue is about capturing the ideas immediately on
  hand, not fleshing out the idea or preparing for implementation.
- Draw relevant information from the conversation when drafting the
  issue.
- Think through what information should and should not be included.
- If input is ambiguous but there is enough to create a placeholder,
  create the issue, add `needs-clarification`, and fill the body using
  best-effort inference.
- Prefer `--body-file` for multi-line bodies.
- Always add the created issue to Bean Lab project `13`.
- If the available `gh issue create` or `gh issue edit` commands cannot
  set the issue type directly, use the GitHub UI or an appropriate
  GitHub API call to set the issue type. Do not consider issue creation
  complete until the GitHub issue type is set.

Create the issue with the correct GitHub issue type, then add it to the
project:

```sh
issue_url="$(gh issue create \
  --title "<title>" \
  --body-file <body-file>)"
# Set the GitHub issue type to Bug, Feature, or Task.
gh project item-add 13 --owner beanlab --url "$issue_url"
```

For unclear input, add the clarification label:

```sh
issue_url="$(gh issue create \
  --title "<title>" \
  --label "needs-clarification" \
  --body-file <body-file>)"
# Set the GitHub issue type to Bug, Feature, or Task.
gh project item-add 13 --owner beanlab --url "$issue_url"
```

## Output

After successful issue creation and project insertion, output only the
GitHub issue URL or issue number/ID.
Do not return the issue body or metadata after creation.

If issue creation succeeds but adding the issue to the project fails,
report the issue URL and the project-add error.
