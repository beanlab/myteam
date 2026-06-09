# Workflows

Workflows are predefined units of execution that have a defined input and output schema.

What follows is a list of workflows available to you, with their descriptions, inputs, and outputs. If a workflow can be used to accomplish your task, please invoke it.

To invoke a workflow, call:
```
myteam start <workflow-name> --input <json-input>
```

The `workflow-name` is the name of the workflow exactly as given below.

Example:
```
myteam start dev/review --input '{"files-changed": ["src/foo.py", "src/bar.py"]}'
```

When a workflow finishes, it will return output that matches the schema described in the workflow description.

A workflow might not have an input or an output defined. If `input` or `output` are not shown with the description, assume these are `null`. You do not need to provide `null` input, and you should ignore `null` output.