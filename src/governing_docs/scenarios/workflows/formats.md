# Workflow Formats

A workflow can be a Python or Markdown file with `type: workflow` in the frontmatter.

### Python

Python workflows are invoked as executable scripts. These use the `run_agent` method to run agent sessions.

The workflow can have any arguments it wants, but these should be described in the module frontmatter `usage` field with sufficient clarity that the caller knows what information to supply.

The workflow can also print anything it wants. All stdout/err printed will be seen by the caller. 

#### Example

```python
"""
type: workflow
description: invoke this workflow only when requested
usage: no arguments
"""

from myteam import run_agent

def main():
    step1 = run_agent(...)
    step2 = run_agent(input=step1.output, ...)
    print(step2.output)

if __name__ == '__main__':
    main()
```

### Markdown

Markdown files are treated as single-step workflows with a single call to `run_agent` made using arguments from the Markdown frontmatter and body.

In Markdown workflows, all `run_agent` arguments except `input` and `prompt` are specified in the frontmatter. The `prompt` argument is the body of the Markdown document. The `input` field in the frontmatter is a schema describing the expected input to the workflow. This input is passed using the `--input` argument when invoking the Markdown workflow.

Additional `run_agent` parameters specified in the frontmatter (e.g. `agent`, `model`, `reasoning`, or `interactive`) will be passed to the underlying invocation of `run_agent`. 

#### Schemas

The input and output schemas in Markdown workflows are not formal jsonschema. Rather, they are human/agent-readable YAML describing what fields are expected and what content should be supplied. They are prompts, not enforcement.

The input schema guides the caller in what data should be passed via the `--input` argument, but it is up to the caller to follow the schema; deviation may result in an error.

Even when an output schema is present, a cleanly quit managed session can return `None`; callers and workflow authors are responsible for deciding how to respond to missing output.

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

