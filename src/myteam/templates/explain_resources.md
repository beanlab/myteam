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

The skill name should be **exactly** what was displayed to you in a `myteam list` command, including the full path and file extension. 

Skills might come with information about additional resources. 
These will be described when you load the skill.

**If you need a skill, use `myteam load <skill>`; do *not* read the skill manually.**

## Workflows

A workflow is a managed agent session or chain of sessions. Workflows are predefined units of execution that can have a defined input and output schema.

If a workflow can be used to accomplish your task, please invoke it. As with all `myteam` resources, **never** assume a task is so trivial that you will do it yourself if there is a workflow that can be used instead.

The `workflow-name` is the name of the workflow exactly as listed.

Markdown workflows accept a single JSON object through `--input`. Use their listed Input and Output schemas to understand what to provide and what result to expect:
```
myteam start <workflow-name> --input '{"field": "value"}'
```

A Markdown invocation can override these agent settings: `--agent`, `--session-name`/`--session_name`, `--model`, `--reasoning`, `--interactive`, `--extra-args`/`--extra_args`, `--session-id`/`--session_id`, and `--fork`. Values use safe YAML syntax and may need shell quoting. Both `--option VALUE` and `--option=VALUE` work; repeated options use the last value.

Settings resolve from workflow frontmatter, then supplied CLI values, then effective home/project defaults for missing or YAML `null` values. A still-missing session name falls back to the workflow path. Effective values must have the expected types; `--fork true` requires an effective `session_id`. Unknown or positional trailing arguments are errors. For example:
```
myteam start review.md --input '{"topic": "release"}' --model gpt-5 --interactive false --extra-args '[--flag, value]'
```

Run `myteam start <markdown-workflow> --help` for generic Markdown workflow option help.

Python workflows may accept arbitrary arguments and options. Follow the listed Usage for each workflow:
```
myteam start <workflow-name> <arguments-or-options>
```

When a workflow finishes, it returns its explicit workflow result text.

Inside a workflow managed by `myteam start`, run `myteam where` to display the active workflow and agent-session hierarchy.

Markdown workflows list Input and Output only when those schemas are specified. If either is absent, do not infer an input requirement or result structure.

When invoking a workflow, do so with a very long timeout (e.g. 2 days). Imposing a time limit will likely result in errors.
