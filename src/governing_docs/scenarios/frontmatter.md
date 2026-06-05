# `myteam` Resource Frontmatter

`myteam` resources contain YAML frontmatter.

Required frontmatter fields:

- `type`: `skill` or `workflow`
- `description`: instructions about how and when an agent should use the resource

Files without the `type` field in the frontmatter will not be treated as `myteam` resources.

`myteam` resources missing the `description` field will result in an error.

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