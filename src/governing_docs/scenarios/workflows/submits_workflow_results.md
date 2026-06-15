# Submits Workflow Results

## Purpose

Submit structured step results.

---

# Context

`myteam workflow-result` is primarily intended for workflow agents running
inside an active workflow step. The active workflow environment provides result
socket metadata and a token that allow the step to submit its final structured
result to the parent workflow runner.

---

# Action

The agent runs `myteam workflow-result [--json <json> | --text <text>]`, or
runs `myteam workflow-result` with JSON provided on standard input.

---

# Interaction

| Action | Outcome |
| --- | --- |
| `--json <json>` | Uses the provided argument as the JSON payload. |
| `--text <text>` | Wraps the text as `{"text": <text>}`. |
| No flag with JSON on standard input | Reads the JSON payload from standard input. |

---

# Outcome

On success, the command reads the workflow result socket path and token from
the current process environment, validates the provided payload input, sends the
payload once to the parent workflow runner for the active step, and prints a
short confirmation message.

The command exits with an error when both `--json` and `--text` are provided,
when no payload is provided and standard input is empty, when the environment
does not contain workflow result socket metadata, when the parent runner
rejects the payload, or when acknowledgement is invalid.

---

# Related Scenarios

- [runs_workflows.md](runs_workflows.md)
- [validates_workflow_definitions.md](validates_workflow_definitions.md)
