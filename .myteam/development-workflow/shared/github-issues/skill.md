---
name: Development Workflow GitHub Issues
description: |
  Standalone GitHub issue and Bean Lab project guidance for the development
  workflow. Load this skill before reading, selecting, creating, or modifying
  GitHub issues for the development workflow.
---

# GitHub Issues

The development workflow backlog is managed with GitHub Issues tracked in the
Bean Lab GitHub Project.

## Authentication

- GitHub issue work uses the `gh` CLI with the current repository by default.
- Check authentication with `gh auth status` when needed.
- If `gh auth status` reports an environment-token problem, verify whether the
  needed `gh` commands actually fail before stopping. Some environments report
  an invalid `GITHUB_TOKEN` while the keychain or approved command path still
  works.
- If the needed `gh` commands cannot authenticate, ask the user to provide a
  GitHub token or authenticate `gh` before proceeding.
- Use `-R OWNER/REPO` when working outside the current repository.

## Project Target

Use the Bean Lab GitHub Project as the project-management surface:

- Project URL: `https://github.com/orgs/beanlab/projects/13`
- Project owner: `beanlab`
- Project number: `13`

Use project item listing as the source of truth for what is currently tracked:

```sh
gh project item-list 13 --owner beanlab --format json
```

## Reading Issues

Useful commands:

```sh
gh issue list --state all --limit 100 --json number,title,state,labels,url,updatedAt
gh issue list --limit 100 --json number,title,state,labels,url,updatedAt
gh issue list --state all --search "<query>" --json number,title,state,labels,url,updatedAt
gh issue view <number-or-url> --comments
gh issue view <number-or-url> --json number,title,body,labels,state,url,comments
gh label list --sort name --limit 200 --json name,description
gh issue status
```

Prefer JSON output when the result will be used for planning, filtering, or
follow-up automation. Use `--comments` when discussion history may affect the
current task.

## Modifying Issues

Use these commands when updating an existing backlog issue:

```sh
gh issue edit <number-or-url> --title "<title>" --body-file <body-file>
gh issue edit <number-or-url> --add-label "needs-clarification"
gh issue comment <number-or-url> --body-file <body-file>
gh issue close <number-or-url> --comment "<short reason>"
gh issue reopen <number-or-url>
```

## Issue Structure

Backlog issues should use this durable base structure:

```md
Created on: <YYYY-MM-DD>
Created by: <user or agent>

## Details

<Overview of the item. Capture the problem, intent, and details currently known.>

## Out-of-scope

<Changes or features left for other backlog items. Reference related issues when known.>

## Dependencies

<Other backlog issues this item depends on. Reference related issues when known.>
```

GitHub also tracks:

- Number or URL: stable identifiers for referencing the issue.
- Title: short summary of the work or problem.
- Type: exactly one of `Touch Code` or `Task`.
- Body: durable backlog description.
- Labels: optional metadata. By default, only use `needs-clarification` when
  the issue is ambiguous or incomplete.
- State: `open` or `closed`.
- Comments: discussion, follow-up, and implementation notes.

Some older backlog issues may follow a different format. If modifying one,
update it as well as possible to match the durable structure and ask the user
for missing information when needed.

Treat backlog issues as placeholders for ideas or TODO items, not implementation
plans. Capture the information immediately on hand from the conversation. Do not
flesh out the idea beyond what is known.

## Creating Issues

Created issues must be added to the Bean Lab GitHub Project:

- Project URL: `https://github.com/orgs/beanlab/projects/13/views/1`
- Project owner: `beanlab`
- Project number: `13`

The token must include the `project` scope. Check with `gh auth status`; add it
with `gh auth refresh -s project` if needed. If `gh auth status` reports an
invalid environment token, verify that the specific `gh` command fails before
stopping.

Every issue must have a GitHub issue type:

- `Touch Code` - any work that involves the code
- `Task` - something that needs doing, but does not involve changing code

For labels, add `needs-clarification` only when the input is ambiguous or
incomplete.

Title rules:

- Use a short imperative summary.
- Do not write a full sentence.
- Prefer concise, action-oriented phrasing when the issue represents work to do.

Creation workflow:

- Create issues automatically once enough input exists; do not add a
  confirmation step.
- Assign the best-fit GitHub issue type.
- If the human owner is known but their GitHub username is not, record the owner
  in the issue body and do not guess an assignee.
- Prefer `--body-file` for multi-line bodies.
- Always add the created issue to Bean Lab project `13`.
- If `gh issue create` or `gh issue edit` cannot set the issue type directly,
  use the GitHub API. Do not consider issue creation complete until the issue
  type is set.

Create the issue, set the issue type, then add it to the project:

```sh
issue_url="$(gh issue create --title "<title>" --body-file <body-file>)"
gh project item-add 13 --owner beanlab --url "$issue_url"
```

For unclear input, add the clarification label:

```sh
issue_url="$(gh issue create --title "<title>" --label "needs-clarification" --body-file <body-file>)"
gh project item-add 13 --owner beanlab --url "$issue_url"
```

If needed, find repository issue type IDs:

```sh
gh api graphql -f query='query {
  repository(owner:"beanlab", name:"myteam") {
    issueTypes(first:20) {
      nodes { id name }
    }
  }
}'
```

Find the issue node ID:

```sh
gh issue view <issue-number-or-url> --json id,number,url
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

Use the target repository in the issue-type query when creating issues outside
`beanlab/myteam`.

## Priority

Backlog priority is a GitHub Project field, not an issue label. When the user
asks for a priority during issue creation, add the issue to the project first,
then update the project item.

Current Bean Lab backlog project IDs:

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

If the fixed IDs stop working, refresh them with:

```sh
gh project field-list 13 --owner beanlab --format json --limit 100
```
