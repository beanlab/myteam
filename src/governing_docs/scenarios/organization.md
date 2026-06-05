# `myteam` Organization

## Location

`myteam` resources are stored under the `.myteam` folder. All resource references must resolve to this folder tree.
References containing `..` or symlinks that resolve outside `.myteam` are invalid.

## Hierarchical organization

Resources are organized hierarchically, following the principle of *progressive disclosure*.

A folder containing `description.md` is a resource namespace. It is displayed in the resource list by the folder name
with the contents of `description.md`.

The `description.md` is a plain Markdown file describing the resource namespace. This text should instruct the agent on
when or why the folder contents should be listed. 

## Naming

The `name` of a skill or workflow is not defined in the YAML frontmatter. It is inferred from the name of the file + relative path from the `.myteam` folder.

For example a skill located at `.myteam/foo/bar.md` would be named `foo/bar.md`.
A workflow located at `.myteam/baz/quux.py` would be named `baz/quux.py`.
A skill located at `.myteam/skill.md` would be named `skill.md`.

Skill and workflow names always include their extensions. References without extensions are assumed to directories. 

Only `.md` and `.py` resource files are supported. Other extensions will result in errors. 

