# Skills

## Format

A skill is a unit of discoverable information that can be loaded on-demand by an agent.

A skill can be:

- a Markdown file with `type: skill` in the YAML frontmatter
- a python file with `type: skill` in the YAML frontmatter stored in the module docstring

The body of the Markdown file becomes the content of the skill.
The stdout of the invoked python script becomes the content of the skill.

### Naming

The `name` of a skill is not defined in the YAML frontmatter. It is inferred from the stem of the file + relative path from the `.myteam` folder.

For example a skill located at `.myteam/foo/bar.md` would be named `foo/bar`.
A skill located at `.myteam/baz/quux.py` would be named `baz/quux.py`.
A skill located at `.myteam/skill.md` would be named `skill`.

### Description

The `description` field of the YAML frontmatter should provide instructions to the agent about when or why to load the skill.

For example:

```
description: Load this skill if you need to construct a git commit
```

### Hierarchical organization

Skills can be organized hierarchically, following the principle of *progressive disclosure*. 

If a folder has a file named `description.md`, then that folder will be displayed as a skill when it's parent folder is listed.

## Explain

`myteam explain skills` should print built-in instructions for how skills work.

These instructions should be clear enough that an agent knows:

- how to list available skills
- how to load a desired skill
- that skills are organized hierarchically
- that `myteam` is preferred for skill management over agent built-in options

## List skills

`myteam get skills [prefix]` should print a list of available skills. 

Each entry should contain:

- skill name: the identifier used to load the skill
- description: instructions that inform the agent about when to load the skill

Because skills are organized hierarchically, `prefix` controls the scope for which the skills are listed.

If `prefix` is not specified, it defaults to empty, meaning the top level of the `.myteam` folder.

#### Examples

Directory setup (assuming all `.md` files shown, except `nope.md` are skill files):

```
.myteam/
  foo/
    description.md
    bar.md
    baz.md
  quux.md
  nope.md
```

`myteam get skills` should print something to the effect of:

```
----foo----
<content from description.md>

----quux---
<description field from quux.md frontmatter>
```

`myteam get skills foo` or `myteam get skills foo/` should print:

```text
----bar----
<description from bar.md>

----baz----
<description from baz.md>
```

`myteam get skills nonsense` should report an error like "Not a skill folder: nonsense".

Whether a skill prefix is valid should be based on whether it resolves to a valid skills folder relative to the `.myteam` folder.

## Load skill

`myteam load <skill>` should load the specified skill by printing the skill content to stdout.

If the specified skill has an extension (e.g. `.md` or `.py`), the specified file is used.

If the skill does not have an extension, `myteam` should try `.py` and `.md` (in that order) until a file is found that matches, which is then loaded.

Python skills are run using the same python executable running `myteam`. Their stdout is returned as the skill content.

Markdown skills are simply printed as-is (but without the YAML frontmatter). 

## New skill

`myteam new skill foo.py` and `myteam new skill foo.md` should create the specified file from the corresponding built-in template for that file extension.

These templates should have the basic structure of what is needed to list and load that skill:

- YAML frontmatter with a `description` field
  - This should be in a `---` block for Markdown files
  - This should be in a `"""` module docstring for Python files
- Markdown skills should have a simple "Not implemented yet" body
- Python skills should have a defined `main()` and `if __name__...` block.
  - `main` should print('Not implemented yet')

