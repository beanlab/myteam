# `myteam` Organization

## Hierarchical organization

Resources are organized hierarchically, following the principle of *progressive disclosure*.

A folder containing `description.md` is a resource namespace. It is displayed in the resource list by the folder name
with the contents of `description.md`.

The `description.md` is a plain Markdown file describing the resource namespace. This text should instruct the agent on
when or why the folder contents should be listed. 

## Naming

The `name` of a skill or workflow is not defined in the YAML frontmatter. Resources are identified by their absolute path or their relative path from the current working directory.

Skill and workflow names always include their extensions. References without extensions are assumed to directories. 

Only `.md` and `.py` resource files are supported. Other extensions will result in errors. 

