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

If `prefix` is not specified, it defaults to empty, meaning the current working directory.

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

`myteam list .myteam` should print something to the effect of:

```
----.myteam/foo/----
<content from description.md>

----workflow: .myteam/go.py----
<description field from go.py frontmatter>

----skill: .myteam/quux.md----
<description field from quux.md frontmatter>
```

`myteam list .myteam/foo` or `myteam list .myteam/foo/` should print:

```text
----skill: .myteam/foo/bar.md----
<description from bar.md>

----skill: .myteam/foo/baz.py----
<description from baz.py>

----workflow: .myteam/foo/yep.py----
<description from yep.py>
```

`myteam list nonsense` should report an error like "Not a skill folder: nonsense".

Any folder can be the prefix in `myteam list`. However, only folders containing `description.md` will be printed as skill folders in the output.

### Listing Python files

When listing Python files, these files are not executed. Rather, only the YAML frontmatter is parsed. 




