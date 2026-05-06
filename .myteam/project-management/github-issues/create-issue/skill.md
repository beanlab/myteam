---
name: "Create Github Issue"
description: "Load this skill when creating a GitHub issue or drafting an issue title, body, type, or labels."
---

## Project Target

Created issues must be added to the Bean Lab GitHub Project:

- Project URL: `https://github.com/orgs/beanlab/projects/13/views/1`
- Project owner: `beanlab`
- Project number: `13`

The token must include the `project` scope. Check with `gh auth status`; add it with `gh auth refresh -s project` if needed.

## Issue Types and Labels

Every issue must have exactly one type label:

- `bug`
- `feature`
- `task`
- `refactor`

Only these labels are allowed by default:

- one issue type label: `bug`, `feature`, `task`, or `refactor`
- `needs clarification`, only when the input is ambiguous or incomplete

Do not add any other labels unless the user explicitly changes this policy.

## Title Rules

- Use a short imperative summary.
- Do not write a full sentence.
- Prefer concise, action-oriented phrasing.

## Body Template

Use this issue body template:

```md
## Purpose
<Clear description of what the issue is about in descriptive sentences>

## Context
<Why this matters, where it occurs, and any relevant system/component context>

## Details
<Technical explanation, logs, code snippets, or implementation notes>

### Reproduction Steps (bugs only)
1.
2.
3.

### Expected Behavior (bugs only)
<What should happen>

### Actual Behavior (bugs only)
<What is currently happening>

## Acceptance Criteria (if applicable)
- [ ]
- [ ]
- [ ]
```

Include `Acceptance Criteria` for features, tasks, and refactors when applicable.
Omit acceptance criteria only when they are not relevant.

## Creation Workflow

- Create issues automatically once enough input exists; do not add a confirmation step.
- Assign the best-fit type label.
- If input is ambiguous, still create the issue, add `needs clarification`, and fill the body using best-effort inference.
- Prefer `--body-file` for multi-line bodies.
- Always add the created issue to Bean Lab project `13`.

Create the issue, then add it to the project:

```sh
issue_url="$(gh issue create --title "<title>" --label "<type>" --body-file <body-file>)"
gh project item-add 13 --owner beanlab --url "$issue_url"
```

For unclear input, add the clarification label:

```sh
issue_url="$(gh issue create --title "<title>" --label "<type>" --label "needs clarification" --body-file <body-file>)"
gh project item-add 13 --owner beanlab --url "$issue_url"
```

## Output

After successful issue creation and project insertion, output only the GitHub issue URL or issue number/ID.
Do not return the issue body or metadata after creation.

If issue creation succeeds but adding the issue to the project fails, report the issue URL and the project-add error.
