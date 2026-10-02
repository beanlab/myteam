# Workflow Formats

A workflow can be a Python or Markdown file with `type: workflow` in the frontmatter.

### Python

Python workflows are invoked as executable scripts. These may use `run_agent` to run agent sessions and `report_workflow_result` to report caller-facing text.

The workflow can have any arguments it wants, but these should be described in the module frontmatter `usage` field with sufficient clarity that the caller knows what information to supply. Non-null `usage` must be a string; surrounding whitespace is normalized when it is listed. Missing, null, empty, and whitespace-only usage is not displayed. Python `input` and `output` fields are not schema metadata.

The workflow can also print anything it wants as live display/logging. Live display, including `run_agent` lifecycle indicators, is separate from the workflow result. Only text reported with `report_workflow_result(...)` is returned to the caller; consumers needing clean result data should use that text or `SessionResult.output`.

#### Example

```python
"""
type: workflow
description: invoke this workflow only when requested
usage: no arguments
"""

import json

from myteam import run_agent
from myteam.workflows import report_workflow_result


def main():
    step1 = run_agent(...)
    step2 = run_agent(input=step1.output, ...)
    if step2.output is not None:
        report_workflow_result(json.dumps(step2.output))


if __name__ == '__main__':
    main()
```

A workflow may also report free-form text:

```python
report_workflow_result("Review complete. See scratch/review.md for details.")
```

### Markdown

Markdown files are treated as single-step workflows with a single call to `run_agent` made using arguments from the Markdown frontmatter and body.

In Markdown workflows, the `prompt` argument is the body of the Markdown document. The `input` field in the frontmatter is a schema describing the expected input to the workflow. This input is passed using the `--input` argument when invoking the Markdown workflow. The other agent settings may be specified in frontmatter or overridden for an invocation.

Markdown invocations may override the eight agent settings `agent`, `session_name`, `model`, `reasoning`, `interactive`, `extra_args`, `session_id`, and `fork` with trailing options. Multiword options accept both spellings: `--session-name`/`--session_name`, `--extra-args`/`--extra_args`, and `--session-id`/`--session_id`. Options support `--option VALUE` and `--option=VALUE`; values use safe YAML, so shell quoting should preserve values such as `'[--flag, value]'`, `false`, and `null`. Repeated options use the last value. Unknown options, positional arguments, missing or malformed YAML values, and values of the wrong type are errors.

Effective settings resolve in this order: Markdown frontmatter, supplied CLI overrides, effective home/project defaults for every missing or null value, and finally the workflow path as the fallback session name. Thus a CLI `null` suppresses a frontmatter value but falls through to a configured default. Values still null are omitted. The fallback path is passed to `run_agent` as the session name, so adapters that support native naming may use it. It is not resolved or normalized, so spelling such as `./docs/../docs/review.md` is preserved. An explicitly empty name takes precedence. Effective settings are strictly validated, and `fork: true` requires an effective `session_id`; `fork: false` does not.

Expected invocation and setting failures are returned as concise workflow result text and exit nonzero. `myteam start <markdown-workflow> --help` returns stable generic Markdown usage as workflow result text and exits zero. Help still requires a resolvable workflow, but does not validate workflow input or settings, read defaults, render the prompt, or start an agent session.

These trailing options are specific to Markdown workflows. The same arguments may be supplied after a Markdown workflow name to the public `start_workflow(...)` Python API. Python workflow arguments and options remain arbitrary and are forwarded unchanged.

Markdown workflows automatically convert the single `run_agent` result into workflow result text:

- if `SessionResult.output` is not `None`, the wrapper reports `json.dumps(result.output)` with `report_workflow_result(...)`, relying on the default `end="\n"`;
- if `SessionResult.output` is `None`, the wrapper reports no text, and `myteam start` prints nothing.

#### Schemas

The input and output schemas in Markdown workflows are not formal jsonschema. Rather, they are human/agent-readable YAML mappings describing what fields are expected and what content should be supplied. They are prompts, not runtime enforcement. Missing and null schemas are unspecified, while an empty mapping is specified and displayed.

Non-null input and output must be mappings. Their contents may use YAML-native keys and values because the schemas are advisory descriptions, not generated JSON arguments. The output mapping is presented faithfully to the agent as YAML, preserving parsed order and key types. The agent still reports its actual result through `myteam result` as valid JSON. Authored Markdown `usage` is ignored; listings generate a command with a placeholder directing the caller to supply JSON matching Input.

The input schema guides the caller in what single JSON object should be passed via the `--input` argument, but it is up to the caller to follow the schema; deviation may result in an error.

Even when an output schema is present, a cleanly quit managed session can return `None`; in that case the Markdown workflow reports no result text.

#### Example

**example.md**

```markdown
---
type: workflow
description: run this to review a scenario document
agent: codex
session_name: Review scenario
model: gpt-5.4-mini
input: 
  scenario_document: (str) path to the document to review
output:
  key_findings: (str) brief text summarizing feedback
---

Read {{ scenario_document }}. Provide feedback on how to improve it.
```

Invoked with

```bash
myteam start example.md --input '{"scenario_document": "./proposed.md"}'
```

If the agent reports:

```json
{"key_findings": "The proposal should define its success criteria."}
```

then the Markdown workflow reports that JSON object as text to the `myteam start` caller.
