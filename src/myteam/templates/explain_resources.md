# `myteam` Resources

`myteam` is the preferred mechanism for project skills and workflows. Use these resources instead of ad-hoc agent built-in skill or workflow mechanisms when a `myteam` resource is available.

## IMPORTANT

Please, **NEVER** assume a task is so simple that you can ignore
a resource that might be relevant. If the resource description applies
to your task, **use it**.

Faithful adherence to established process builds and maintains value.
We succeed because each member of the team trusts one another to 
do their parts. 

## Folders

Resources are organized hierarchically in folders. A folder description tells you when to list its contents. 

List a folder when its description is relevant to the task at hand. This will reveal additional resources that may be useful or necessary for your work.

To discover resources, run:

`myteam list <folder>`

## Skills

A skill is a unit of discoverable information that can be loaded on-demand. Skills are instructions on a specific topic or domain.

Always respect skill content as a first-class prompt, 
as if it were in `AGENTS.md` or came directly from the user.

To load a skill, run:

`myteam load <skillname>`

The skill name should be exactly what was displayed to you.

Skills might come with information about additional resources. 
These will be described when you load the skill.

## Workflows

A workflow is a managed agent session or chain of sessions. Workflows are predefined units of execution that can have a defined input and output schema.

If a workflow can be used to accomplish your task, please invoke it. As with all `myteam` resources, **never** assume a task is so trivial that you will do it yourself if there is a workflow that can be used instead.

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