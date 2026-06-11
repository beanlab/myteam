# Workflows

Workflows are chained, managed agent sessions.

While agents can follow a process defined in Markdown text, they can also deviate from the intended instructions. Workflows provide a more structured execution of instructions than freely-interpreted text. 
 
## `run_agent`

`myteam` provides a function named `run_agent` that launches a child agent CLI session. 

See also `agent-session-management.md`. 

`UsageInfo` described in `usage.md`

```python
class SessionResult:
    output: dict[str, Any] | None
    usage: list[UsageInfo]
    transcript: str
    session_id: str
    
def run_agent(
        *,
        prompt: str,
        input: dict[str, Any] = None,
        output: dict[str, Any] | None = None,
        agent: str | None = None,
        model: str | None = None,
        reasoning: str | None = None,
        extra_args: tuple[str, ...] | None = None,
        interactive: bool | None = None,
        session_id: str | None = None,
        fork: bool | None = None,
    ) -> SessionResult:
```

- `prompt`: the instructions passed to the agent session
- `input`: the input to the workflow
- `output`: a basic schema describing the required output content and format
- `agent`: the name of the agent executable to use (e.g. `codex` or `claude`)
- `model`: the model used by the session (e.g. 'gpt-5.4-mini')
- `reasoning`: reasoning level for the model (e.g. 'medium')
- `interactive`: controls whether the agent session supports human interaction or runs in headless mode
- `extra_args`: additional command-line arguments to be passed to the agent session; this gives developers additional control over session customization
- `session_id`: indicates the prior agent session to resume; this value is whatever session ID the agent uses and can be obtained from a prior `SessionResult`
- `fork`: determines whether the specified session is forked or resumed. When `False`, the session is resumed in place; when `True`, it is forked and a new session is created from the history of the specified session. Fork is examined only if `session_id` is provided. 

## Format

A workflow can be a Markdown or Python file with `type: workflow` in the frontmatter.

### Markdown

Markdown files are treated as single-step workflows. 

In Markdown workflows, all `run_agent` arguments except `prompt` can be specified in the frontmatter. 

The prompt for the agent session is the document body with the `--input` keys injected via `jinja2` rendering—i.e. the keys of the input object will all be available as variables in the jinja template.

In effect (pseudocode):

```
frontmatter, body = split_markdown(markdown_file_text)
prompt = jinja.render(body, **runtime_input)
```

Additional `run_agent` parameters specified in the frontmatter (e.g. `agent`, `model`, `reasoning`, or `interactive`) will be passed to the underlying invocation of `run_agent`. 

#### Example

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

### Python

Python workflows are invoked as executable scripts.

These use the `run_agent` method to run agent sessions.

They support an `--input <input>` argument through which the `input` content described in the frontmatter can be passed.

A decorator named `@workflow` is provided to adapt a workflow `main` method to the expected input signature and output behavior. It will expose a `--input <JSON>` argument on the commandline and expects `main` to return a `SessionResult` object.

```python
"""
type: workflow
description: invoke this workflow only when requested
"""

from myteam import run_agent, workflow

@workflow
def main(workflow_input):
    step1 = run_agent(...)
    step2 = run_agent(input=step1.output, ...)
    return step2

if __name__ == '__main__':
    main()
```

Python workflows that are not authored with `@workflow` should provide their own support for `--input <JSON>` and printing the output to stdout in JSON format. 

The frontmatter `input` and `output` fields describe the expected input and output of the workflow as a whole, not the individual calls to `run_agent` inside the workflow.

As all the other `run_agent` arguments apply specifically to an agent session and don't make sense at the outer workflow level, Python workflows do not support these fields in the frontmatter. 

In other words, only `type`, `description`, `input`, and `output` are supported in Python workflow frontmatter.

### Schemas

The input and output schemas are not formal jsonschema. Rather, they are human-readable YAML describing what fields are expected and what content should be supplied.

The input schema guides the caller in what data should be passed via the `--input` argument.

The output schema is intended more as prompt for the agent than as output-shape enforcement. Even when an output schema is present, a cleanly quit managed session can return `None`; callers and workflow authors are responsible for deciding how to respond to missing output.

In Markdown workflows, there is only one step, so the strict output shape is less critical.

Multistep workflows—where one step depends on the reliable shape of prior step output—are always written in Python. In this case, the author may use the preferred method for both describing the output and enforcing its compliance.

## Start

See `start.md`

## New

`myteam new workflow <workflow>` creates a new workflow file from the respective template. 

If `<workflow>` ends in `.md`, it uses the Markdown template. If `<workflow>` ends in `.py`, it uses the Python template. Other extensions result in an error.
