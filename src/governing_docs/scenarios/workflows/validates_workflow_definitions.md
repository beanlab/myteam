# Validates Workflow Definitions

## Purpose

Define authored workflow shape.

---

# Context

YAML workflow files are user-authored files stored in the selected local root.
They define ordered workflow steps and may reference completed state from
earlier steps.

---

# Action

The caller starts a YAML workflow or otherwise causes `myteam` to load and
validate a YAML workflow definition.

---

# Interaction

| Action | Outcome |
| --- | --- |
| Top-level YAML mapping | Each top-level key is treated as a workflow step name. |
| Step mapping with `prompt`, optional `input`, optional `agent`, and `output` | The step is valid when all workflow shape rules are satisfied. |
| Omitted `agent` | The default shipped agent is used. |
| `output` mapping with nested objects | The final step result must contain the same nested keys. |
| Output-template leaf values | Leaf values are treated as descriptive placeholders and do not constrain the final JSON value type. |
| Full-string reference such as `$step.output.value` inside `input` | Resolves against previously completed step state and inserts the resolved value as structured data. |
| Exact scalar value `$$` prefix | Escapes a literal leading dollar. |

---

# Outcome

Workflow files do not use a top-level `steps:` wrapper. Steps execute in the
order they are authored in the file. Step names and authored nested keys that
participate in the workflow format and reference system must use valid
identifier-style names.

Reference expressions start with `$`. The token immediately after `$` is the
earlier step name. Additional dotted path components select nested object keys
from that step's stored completed state. References resolve only against
previously completed steps. Objects and arrays remain objects and arrays when
inserted through a reference.

Missing paths are errors. Reference traversal supports object keys, not array
indexes. Partial string interpolation is not supported. Forward references and
self-references are invalid at execution time.

The step agent must report the final structured result through
`myteam workflow-result` rather than terminal markers or free-form prose.

---

# Related Scenarios

- [runs_workflows.md](runs_workflows.md)
- [submits_workflow_results.md](submits_workflow_results.md)
