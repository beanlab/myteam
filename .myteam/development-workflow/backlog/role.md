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

## New Item

First read `application_interface.md` to understand the current design and 
intent of the project. Then ask the user questions to understand what they
want to change. Is it a new behavior? Modifying an existing behavior? A bugfix?

Create the new issue with an appropriate name.
Edit the issue body so it contains the required workflow sections supplied in the input.

Return `start_step` as `design-conversation`.

## Existing Item

Identify the GitHub issue for this development workflow from the Bean Lab
project, edit the issue body so it contains the required workflow sections
supplied in the input, and return the issue identifiers and a concise
backlog summary using the output schema.

Choose and return `start_step` as `design-conversation`,
`scenario_conversation`, `implement-conversation`, `implement`, or
`review`. Do not return `wrap_up` as the starting step.

Choose the earliest step that still needs meaningful work, unless the user has
explicitly asked to resume at a later allowed step. Use `review` when the issue
already has sufficient scenarios, design, and implementation context and the
next useful action is review.

# Github Issues

## Authentication

- GitHub issue work uses the `gh` CLI with the current repository
  by default.
- Check authentication with `gh auth status` when needed.
- If `gh auth status` reports an environment-token problem, verify
  whether the needed `gh` commands actually fail before stopping. Some
  environments report an invalid `GITHUB_TOKEN` while the keychain or
  approved command path still works.
- If the needed `gh` commands cannot authenticate, ask the user to
  provide a GitHub token or authenticate `gh` before proceeding.
- Use `-R OWNER/REPO` when working outside the current repository.

## Project Target

These skills use the Bean Lab GitHub Project as the
project-management surface:

- Project URL: `https://github.com/orgs/beanlab/projects/13`
- Project owner: `beanlab`
- Project number: `13`

Use project item listing as the source of truth for what is currently
tracked in the backlog:

```sh
gh project item-list 13 --owner beanlab --format json
```

## Reading Issues

Use these commands to inspect the issue tracker:

- List all available issues:
  ```sh
  gh issue list \
    --state all \
    --limit 100 \
    --json number,title,state,labels,url,updatedAt
  ```
- List open issues:
  ```sh
  gh issue list \
    --limit 100 \
    --json number,title,state,labels,url,updatedAt
  ```
- Search issues:
  ```sh
  gh issue list \
    --state all \
    --search "<query>" \
    --json number,title,state,labels,url,updatedAt
  ```
- View an issue with comments:
  `gh issue view <number-or-url> --comments`
- View structured issue data:
  ```sh
  gh issue view <number-or-url> \
    --json number,title,body,labels,state,url,comments
  ```
- List repository labels:
  `gh label list --sort name --limit 200 --json name,description`
- Show issues relevant to the authenticated user:
  `gh issue status`

## Modifying Issues

Use these commands when updating an existing backlog issue:

- Edit title, labels, or body:
  ```sh
  gh issue edit <number-or-url> \
    --title "<title>" \
    --body-file <body-file> \
    --add-label "<label>"
  ```
- Add a discussion note or clarification:
  `gh issue comment <number-or-url> --body-file <body-file>`
- Close a completed or obsolete issue:
  `gh issue close <number-or-url> --comment "<short reason>"`
- Reopen an issue:
  `gh issue reopen <number-or-url>`

## Issue Structure

Backlog issues should use this durable structure:

```md
Created on: <YYYY-MM-DD>
Created by: <user or agent>

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

GitHub also tracks:

- Number or URL: stable identifiers for referencing the issue.
- Title: short summary of the work or problem.
- Type: exactly one of `Touch Code` or `Task`.
- Body: durable backlog description using the structure above.
- Labels: optional metadata used for filtering. By default, only use
  `needs-clarification` when the issue is ambiguous or incomplete.
- State: `open` or `closed`.
- Comments: discussion, follow-up, and implementation notes.

Some older backlog issues may follow a different format. If you modify
one, update it as best you can to match this format and ask the user
for missing information when needed.

## Guidance

- Prefer JSON output when the result will be used for planning,
  filtering, or follow-up automation.
- Use `--comments` when discussion history may affect the current
  task.
- Check labels before assuming available workflow categories.
- Treat the issue body as the source of durable requirements; comments
  may contain later clarifications.
- Treat backlog issues as placeholders for ideas or TODO items, not
  implementation plans.
- Capture the information immediately on hand from the conversation.
- Think through what information should and should not be included.
  Do not flesh out the idea beyond what is known.
- Keep implementation details in the issue only when they already
  exist or are necessary context.

## Creating Issues

Created issues must be added to the Bean Lab GitHub Project:

- Project URL: `https://github.com/orgs/beanlab/projects/13/views/1`
- Project owner: `beanlab`
- Project number: `13`

The token must include the `project` scope. Check with
`gh auth status`; add it with `gh auth refresh -s project` if needed.
If `gh auth status` reports an invalid environment token, verify that
the specific `gh` command fails before stopping. Some environments have
an invalid `GITHUB_TOKEN` while another authenticated path still lets
the necessary command complete.

## Issue Types and Labels

Every issue must have a GitHub issue type:

- `Touch Code` - any work that involves the code
- `Task` - something that needs doing, but doesn't involve changing code

For labels, add `needs-clarification` only when the input is ambiguous
or incomplete.

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
- If the human owner is known but their GitHub username is not, record
  the owner in the issue body and do not guess an assignee. Assign the
  issue only when the username is known.
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
# Set the GitHub issue type to `Task` or `Touch Code`, then add it.
gh project item-add 13 --owner beanlab --url "$issue_url"
```

For unclear input, add the clarification label:

```sh
issue_url="$(gh issue create \
  --title "<title>" \
  --label "needs-clarification" \
  --body-file <body-file>)"
# Set the GitHub issue type to `Task` or `Touch Code`, then add it.
gh project item-add 13 --owner beanlab --url "$issue_url"
```

If `gh issue create` and `gh issue edit` cannot set the GitHub issue
type directly, use the GraphQL API.

Find the repository issue type ID:

```sh
gh api graphql \
  -f query='query {
    repository(owner:"beanlab", name:"myteam") {
      issueTypes(first:20) {
        nodes { id name }
      }
    }
  }'
```

Find the issue node ID:

```sh
gh issue view <issue-number-or-url> \
  --json id,number,url
```

Set the issue type:

```sh
gh api graphql \
  -f query='mutation($id:ID!, $type:ID!) {
    updateIssue(input:{id:$id, issueTypeId:$type}) {
      issue { number issueType { name } }
    }
  }' \
  -f id=<issue-node-id> \
  -f type=<issue-type-id>
```

Use the target repository in the issue-type query when creating issues
outside `beanlab/myteam`.

## Priority

Backlog priority is a GitHub Project field, not an issue label. When
the user asks for a priority during issue creation, add the issue to
the project first, then update the project item.

Use these current IDs for the Bean Lab backlog project:

- Project ID: `PVT_kwDOCA0Mqs4BW0Oo`
- Priority field ID: `PVTSSF_lADOCA0Mqs4BW0OozhSFeN8`
- `P0` option ID: `79628723`
- `P1` option ID: `0a877460`
- `P2` option ID: `da944a9c`

Find the project item, then set the requested priority:

```sh
gh project item-list 13 \
  --owner beanlab \
  --format json \
  --jq '.items[] | select(.content.number == <issue-number>)'

gh project item-edit \
  --id <project-item-id> \
  --project-id PVT_kwDOCA0Mqs4BW0Oo \
  --field-id PVTSSF_lADOCA0Mqs4BW0OozhSFeN8 \
  --single-select-option-id <priority-option-id>
```

If the fixed IDs stop working, refresh them with
`gh project field-list 13 --owner beanlab --format json --limit 100`.
