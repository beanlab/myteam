# `myteam` Resource Frontmatter

`myteam` resources contain YAML frontmatter.

The `type` field in the frontmatter is required. Its values can be `skill` or `workflow`.
Files without the `type` field in the frontmatter will not be treated as `myteam` resources.

The `description` field is encouraged but optional. It provides instructions about how and when an agent should use the resource

`myteam` resources missing the `description` field will have an empty description when listed.

Recognized workflows have format-specific optional metadata:

- Python `usage`, when non-null, must be a string. Python `input` and `output` have no schema meaning and are not validated as schemas.
- Markdown `input` and `output`, when non-null, must be mappings. Their keys and values may use YAML-native types. Markdown `usage` is ignored because invocation usage is generated from `input`.

Missing and null fields are unspecified. Empty mappings are specified schemas. Invalid recognized workflow fields prevent both listing and starting that workflow.

In Markdown files, the frontmatter is in the standard `---` block at the beginning of the file.

```markdown
---
type: skill
description: load this skill if you need to use `git`
---
`git` is used for source control...
```

In Python files, the frontmatter is stored in the module docstring:

```python
"""
type: skill
description: load this skill if you need to use `git`
"""
from pathlib import Path
def main():
    print(Path('git_instructions.md').read_text())
```