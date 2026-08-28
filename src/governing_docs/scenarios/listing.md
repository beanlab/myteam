# Listing Skills and Workflows

`myteam list [TARGET ...]` displays skill and workflow resources selected by zero or more file or directory targets.

A user or agent references a `myteam` resource by the path displayed when listed. Results from all targets are deduplicated and sorted globally by name, with folders, skills, and workflows sorted together.

Each folder entry contains its path and the content of its `description.md`. Each skill or workflow entry contains its path and the `description` from its frontmatter. Python resource files are parsed, not executed.

## Selecting resources

- A file target selects that file.
- A directory target selects its immediate children; listing is not recursive.
- `-d` or `--directory` selects each target itself instead. A selected directory is listed only when it contains `description.md`.
- With no targets, the current working directory is used. Therefore, plain `myteam list` lists its immediate children, while `myteam list -d` evaluates the current directory itself.

One resource may be reached through repeated, overlapping, or symlink-aliased targets. It is emitted only once. Symlinks are followed and displayed using the same canonical path behavior as other listings.

Existing unsupported files, files without valid resource frontmatter, and directories without `description.md` are ignored. A valid selection containing no resources succeeds with empty output.

Targets are literal paths. The shell is responsible for glob expansion, unmatched patterns, and whether hidden files are included. For example, after shell expansion, `myteam list agents/*` passes each match as a separate target.

If any target or selected resource is missing, unreadable, otherwise inaccessible, or has invalid recognized workflow metadata, listing fails without printing a partial resource list. A metadata diagnostic identifies the file, field, actual type, and expected type.

## Python API

```python
from myteam import list_resources

text = list_resources(*targets, directory=False)
```

Each target may be a string or path. The API follows the same file and directory selection rules as `myteam list`; passing `directory=True` selects targets themselves. It aggregates, deduplicates, globally sorts, and formats results like the CLI.

Calling `list_resources()` without a target uses the current working directory. Existing positional single-target calls such as `list_resources("agents")` remain supported.

A missing, unreadable, or otherwise inaccessible path, or invalid selected workflow metadata, writes a diagnostic to stderr and raises `SystemExit(1)`. No partial listing is returned.

## Output format

Given:

```
agents/
  foo/
    description.md
    bar.md  # skill
    baz.py  # skill
    yep.py  # workflow
  quux.md  # skill
  go.py    # workflow
```

`myteam list agents` prints the immediate resources:

```text
----agents/foo/----
<content from description.md>

----workflow: agents/go.py----
<description field from go.py frontmatter>

----skill: agents/quux.md----
<description field from quux.md frontmatter>
```

`myteam list agents/foo` prints its immediate resources:

```text
----skill: agents/foo/bar.md----
<description from bar.md>

----skill: agents/foo/baz.py----
<description from baz.py>

----workflow: agents/foo/yep.py----
<description from yep.py>
```

`myteam list agents/foo/bar.md` prints only the `bar.md` block. `myteam list -d agents/foo` prints only the folder block for `agents/foo`.

### Workflow details

Workflow details follow the description, with a blank line between the description and each section. Sections are ordered `Usage`, `Input`, then `Output`.

For a Python workflow, non-empty `usage` is stripped of surrounding whitespace and displayed without changing its internal or multiline content:

```text
----workflow: agents/review.py----
Review changes.

Usage:
review.py --scope PATH
```

Missing, null, empty, or whitespace-only Python usage is omitted.

For a Markdown workflow, specified input and output mappings are displayed as normalized block YAML, preserving parsed key order and nesting. An input mapping also generates a POSIX-shell-actionable command using the actual displayed workflow path and a fixed placeholder for caller-supplied JSON:

```text
----workflow: agents/review.md----
Review changes.

Usage:
myteam start agents/review.md --input '<JSON matching Input>'

Input:
scope: path to review

Output:
summary: review summary
```

An empty mapping is specified and is displayed as `{}`; an empty input mapping also generates Usage. Missing or null fields are unspecified and omitted. An output-only Markdown workflow has an Output section but no generated Usage. Authored Markdown `usage` is ignored. Input is the sole schema description; generated Usage does not derive argument contents from schema values. Generated commands independently POSIX-quote the displayed path and the literal `<JSON matching Input>` placeholder, which the caller replaces with a JSON object. They are not promised to be portable to non-POSIX shells.

The CLI, `list_resources()`, and Jinja `myteam_list()` produce exactly equivalent enriched text for the same selected resources.
