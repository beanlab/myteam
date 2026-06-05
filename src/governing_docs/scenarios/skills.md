# Skills

## Format

A skill is a unit of discoverable information that can be loaded on-demand by an agent.

A skill can be:

- a Markdown file with `type: skill` in the YAML frontmatter
- a Python file with `type: skill` in the YAML frontmatter stored in the module docstring

The body of the Markdown file becomes the content of the skill.
The stdout of the invoked Python script becomes the content of the skill.

Files without the `type: skill` frontmatter will not be treated as skills.

Only `.md` and `.py` skill files are supported. Other extensions will result in errors. 

### Naming

The `name` of a skill is not defined in the YAML frontmatter. It is inferred from the name of the file + relative path from the `.myteam` folder.

For example a skill located at `.myteam/foo/bar.md` would be named `foo/bar.md`.
A skill located at `.myteam/baz/quux.py` would be named `baz/quux.py`.
A skill located at `.myteam/skill.md` would be named `skill.md`.

### Description

The `description` field of the YAML frontmatter should provide instructions to the agent about when or why to load the skill.

For example:

```
description: Load this skill if you need to construct a git commit
```

The `description` is a required field. Files specified as skills that are missing `description` will result in an error.

### Hierarchical organization

Skills can be organized hierarchically, following the principle of *progressive disclosure*. 

A folder containing `description.md` is a skill namespace. It is displayed in the skill list by the folder name and the contents of `description.md`.

The `description.md` is a plain Markdown file describing the skill namespace. This text should instruct the agent on when or why the skill namespace should be viewed. Viewing the namespace will list the sub-skills in that namespace. 

### Location

Skills are stored under the `.myteam` folder. All skill references must resolve to this folder tree. References containing `..` or symlinks that resolve outside `.myteam` are invalid.

## Explain

`myteam explain skills` should print built-in instructions for how skills work.

These instructions should be clear enough that an agent knows:

- how to list available skills
- how to load a desired skill
- that skills are organized hierarchically
- that `myteam` is preferred for skill management over agent built-in options

## List skills

`myteam list skills [prefix]` should print a list of available skills and skill folders. 

Each skill entry should contain:

- skill name: the identifier used to load the skill
- description: instructions that inform the agent about when to load the skill

Each skill folder entry should contain:
- folder name: the identifier used to list additional skills
- description: instructions that inform the agent about when to list these additional skills

Because skills are organized hierarchically, `prefix` controls the scope for which the skills are listed.

If `prefix` is not specified, it defaults to empty, meaning the top level of the `.myteam` folder.

Skill entries are listed in alphabetical order by skill name with folders and files sorted together.

### Examples

Directory setup:

```
.myteam/
  foo/
    description.md
    bar.md  # skill
    baz.md  # skill
  quux.md  # skill
  nope.md
```

`myteam list skills` should print something to the effect of:

```
----foo/----
<content from description.md>

----quux.md----
<description field from quux.md frontmatter>
```

`myteam list skills foo` or `myteam list skills foo/` should print:

```text
----bar.md----
<description from bar.md>

----baz.md----
<description from baz.md>
```

`myteam list skills nonsense` should report an error like "Not a skill folder: nonsense".

The root `.myteam` folder is always a valid skill listing prefix. A non-root prefix is valid if it resolves to a directory under `.myteam` containing `description.md`.
### Listing Python skills

When listing skills, Python skills are not executed. Rather, only the YAML frontmatter is parsed. 

## Load skill

`myteam load <skill>` should load the specified skill by printing the skill content to stdout.

Markdown skills are simply printed as-is (but without the YAML frontmatter). 

Python skills are run using the same Python executable running `myteam` with the skill's directory as the working directory and environment variables inherited. Their stdout is returned as the skill content.

If the Python process exits non-zero, `myteam load` should print stderr and exit non-zero. This allows the agent to inform the user of the issue. Any captured stdout is omitted. 

Python skills do not support command-line arguments.

`myteam load ...` does not validate the YAML frontmatter. It simply attempts to load the specified file according to its extension.

`myteam load <folder>` should raise an error explaining that `myteam list skills <folder>` should be used instead.

## New skill

`myteam new skill foo.py` and `myteam new skill foo.md` should create the specified file from the corresponding built-in template for that file extension.

These templates should have the basic structure of what is needed to list and load that skill:

- YAML frontmatter with `type: skill` and a stubbed `description: ...`
  - This should be in a `---` block for Markdown files
  - This should be in a `"""` module docstring for Python files
- Markdown skills should have a simple "Not implemented yet" body
- Python skills should have a defined `main()` and `if __name__...` block.
  - `main` should print('Not implemented yet')

`myteam new skill` will create parent directories as needed, each new directory created with a stubbed `description.md` (existing directories and descriptions are unchanged). 

If the target skill file already exists, `myteam new skill` raises an error.

`myteam new skill foo` will assume `foo` is a skill folder and create that folder with a stubbed `description.md`.

The default `description.md` content should contain a warning message alerting the user/agent that the description has not been written.