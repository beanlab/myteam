# Workflow Formats

A workflow can be a Python or Markdown file with `type: workflow` in the frontmatter.

### Python

Python workflows are invoked as executable scripts. These may use `run_agent` to run agent sessions and `report_workflow_result` to report caller-facing text.

The workflow can have any arguments it wants, but these should be described in the module frontmatter `usage` field with sufficient clarity that the caller knows what information to supply.

The workflow can also print anything it wants as live display/logging. Printed stdout/stderr is not returned by `myteam start`; only text reported with `report_workflow_result(...)` is returned to the caller.

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

In Markdown workflows, all `run_agent` arguments except `input` and `prompt` are specified in the frontmatter. The `prompt` argument is the body of the Markdown document. The `input` field in the frontmatter is a schema describing the expected input to the workflow. This input is passed using the `--input` argument when invoking the Markdown workflow.

Additional `run_agent` parameters specified in the frontmatter (e.g. `agent`, `model`, `reasoning`, or `interactive`) will be passed to the underlying invocation of `run_agent`.

Markdown workflows automatically convert the single `run_agent` result into workflow result text:

- if `SessionResult.output` is not `None`, the wrapper reports `json.dumps(result.output)` with `report_workflow_result(...)`, relying on the default `end="\n"`;
- if `SessionResult.output` is `None`, the wrapper reports no text, and `myteam start` prints nothing.

#### Schemas

The input and output schemas in Markdown workflows are not formal jsonschema. Rather, they are human/agent-readable YAML describing what fields are expected and what content should be supplied. They are prompts, not enforcement.

The input schema guides the caller in what data should be passed via the `--input` argument, but it is up to the caller to follow the schema; deviation may result in an error.

Even when an output schema is present, a cleanly quit managed session can return `None`; in that case the Markdown workflow reports no result text.

#### Example

**example.md**

```markdown
---
type: workflow
description: run this to review a scenario document
agent: codex
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
