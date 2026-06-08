# Skills

A skill is a unit of discoverable information that can be loaded on-demand by an agent.

## Format

A skill can be a Markdown or Python file with `type: skill` in the frontmatter.

The body of the Markdown file becomes the content of the skill.

The stdout of the invoked Python script becomes the content of the skill.

The `description` field is encouraged, but optional. 

## Load skill

`myteam load <skill>` should load the specified skill by printing the skill content to stdout.

Markdown skills are simply printed as-is (but without the YAML frontmatter). 

Python skills are run using the same Python executable running `myteam` with the skill's directory as the working directory and environment variables inherited. Their stdout is returned as the skill content.

If the Python process exits non-zero, `myteam load` should print stderr and exit non-zero. This allows the agent to inform the user of the issue. Any captured stdout is omitted. 

Python skills do not support command-line arguments.

`myteam load ...` does not validate the YAML frontmatter. It simply attempts to load the specified file according to its extension. So it is possible to load a file that is not formatted with valid frontmatter.

`myteam load <folder>` should raise an error explaining that `myteam list <folder>` should be used instead.

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