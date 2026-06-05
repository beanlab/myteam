# Listing Skills and Workflows

`myteam list [prefix]` displays a list of the skills and workflows available under the specified prefix.

Entries are listed in alphabetical order by name with folders, files, and workflows sorted together.

Each folder entry should contain:

- folder name: the identifier used to list nested content
- description: instructions that inform the agent about when to list this additional content

Each skill entry should contain:

- skill name: the identifier used to load the skill
- description: instructions that inform the agent about when to load the skill

Each workflow entry should contain:

- workflow name: the identifier used to start the workflow
- description: instructions that inform the agent about when and how to use the workflow

Because skills and workflows are organized hierarchically, `prefix` controls the scope for which the items are listed.

If `prefix` is not specified, it defaults to empty, meaning the top level of the `.myteam` folder.

### Examples

Directory setup:

```
.myteam/
  foo/
    description.md
    bar.md  # skill
    baz.py  # skill
    yep.py  # workflow
  quux.md  # skill
  nope.md
  go.py    # workflow
```

`myteam list` should print something to the effect of:

```
----foo/----
<content from description.md>

----workflow: go.py----
<description field from go.py frontmatter>

----skill: quux.md----
<description field from quux.md frontmatter>
```

`myteam list foo` or `myteam list foo/` should print:

```text
----skill: bar.md----
<description from bar.md>

----skill: baz.md----
<description from baz.md>

----workflow: yep.py----
<description from yep.py>
```

`myteam list nonsense` should report an error like "Not a skill folder: nonsense".

The root `.myteam` folder is always a valid listing prefix. A non-root prefix is valid if it resolves to a directory under `.myteam` containing `description.md`.

### Listing Python files

When listing Python files, these files are not executed. Rather, only the YAML frontmatter is parsed. 




