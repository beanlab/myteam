# Workflows

Workflows are predefined units of execution that have a defined input and output schema.

What follows is a list of workflows available to you, with their descriptions, inputs, and outputs. If a workflow can be used to accomplish your task, please invoke it.

To invoke a workflow, call:
```
myteam workflow start <workflow-name> --session-nonce <session_nonce> --input <json-input>
```

The `workflow-name` is the name of the workflow exactly as given below.
The `session_nonce` is the same one you were given at the start of this session.
Pass the workflow input as JSON for the `input` argument.

Example:
```
myteam workflow start dev/review --session-nonce 12345678-2345-3456-1234-12345678 --input '{"files-changed": ["src/foo.py", "src/bar.py"]}'
```

When a workflow finishes, it will return output that matches the schema described in the workflow description.

A workflow might not have an input or an output defined. If `input` or `output` are not shown with the description, assume these are `null`. You do not need to provide `null` input, and you should ignore `null` output.