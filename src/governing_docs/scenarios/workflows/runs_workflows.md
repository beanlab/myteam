# Runs Workflows

## Purpose

Execute authored workflows.

---

# Context

Workflow definitions are stored in the selected local root. A workflow path is
slash-delimited, such as `dev/frontend`, and resolves to a supported workflow
file in that local root.

Supported workflow files include YAML files ending in `.yaml` or `.yml` and
Python workflow files ending in `.py`.

---

# Action

The caller runs `myteam start <path> [--prefix <path>] [--verbose]`.

---

# Interaction

| Action | Outcome |
| --- | --- |
| Start a YAML workflow | Loads and validates the authored YAML definition, executes steps in authored order, supplies each configured workflow agent with the authored step prompt, stores completed step state for later references, and returns success only after all steps complete. |
| Start a Python workflow | Executes the workflow file as a separate Python process using the active Python executable and propagates the process exit status. |
| A step fails | Stops at the first failing step, does not execute later steps, and exits with an error. |
| `--verbose` | Enables workflow lifecycle logging on standard error. |

---

# Outcome

Workflow execution mirrors the child session's terminal output to standard
output as the workflow runs and reports command failures on standard error.

Successful YAML workflow completion does not currently emit an additional final
workflow-result payload on standard output.

For Python workflows, the child process working directory is the directory
containing the workflow file. The Python workflow is responsible for invoking
its own entry point, such as with an `if __name__ == "__main__":` block.

The command exits with an error when the workflow path does not resolve to a
workflow file with a supported extension, when the workflow definition is
malformed, when the definition references an unknown agent, when any workflow
step fails, or when a Python workflow process exits non-zero.

---

# Related Scenarios

- [validates_workflow_definitions.md](validates_workflow_definitions.md)
- [submits_workflow_results.md](submits_workflow_results.md)
- [../local_tree/uses_selected_local_root.md](../local_tree/uses_selected_local_root.md)
