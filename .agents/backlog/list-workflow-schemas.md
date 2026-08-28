# Include workflow schemas in `myteam list`

## Problem

`myteam explain` tells agents that a workflow listing may include `input` and `output` schemas, but `myteam list` currently prints only the workflow's frontmatter `description`. Callers therefore cannot discover the data required to start a workflow or the result it returns from the normal resource-discovery command.

This conflicts with the instruction to invoke workflows using the schema shown in their description.

## Proposal

When `myteam list` prints a workflow, include its frontmatter `input` and `output` schemas after the description. Preserve their structure in a concise, unambiguous representation. Skills and folders should retain their current output.

Treat omitted schemas as absent rather than printing noise. Explicit `null` schemas may also be omitted because `myteam explain` already defines an unshown schema as `null`.

Apply the behavior consistently to Markdown and Python workflow frontmatter without executing Python resources.

## Acceptance criteria

- Listed workflows show their non-null `input` and `output` schemas.
- Nested schema structures remain readable and retain field names, types, and descriptions.
- Workflows without schemas keep concise listings.
- Skill and folder listing output is unchanged.
- Python workflows remain parsed without execution.
- The CLI and `list_resources()` Python API produce equivalent output.
- Governing documentation and public contract tests describe and protect the format.
