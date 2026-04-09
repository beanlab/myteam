# Loader Template Exports

## Summary

The installed package does not expose the loader templates as a direct, stable package interface.

Right now, the templates exist inside `src/myteam/templates/`, but callers appear to reach them only
indirectly through command helpers such as `get_template(...)` in `commands.py`.

That makes the template layer harder to discover, harder to reuse from external code, and less
clear as a supported part of the package surface.

## Problem

Loader templates are part of the package's authoring story:

- `root_role_load_template.py`
- `role_load_template.py`
- `skill_load_template.py`
- built-in skill loader templates

But the package complaint is reasonable: an installed consumer cannot obviously import or enumerate
these templates as named package resources.

This creates a few practical issues:

- template access feels implementation-shaped rather than intentional
- downstream code has to know internal template names and helper behavior
- refactors to internal file layout risk breaking consumers even when the logical template set has
  not changed
- documentation cannot point to a clear supported access pattern for loader templates

## Goals

- Expose loader templates through a direct, documented package interface.
- Make installed-package behavior as clear as editable-source behavior.
- Keep template access stable even if internal file layout changes later.
- Avoid forcing consumers to depend on command-layer internals just to fetch template content.

## Proposed Direction

Provide an explicit template-access API for installed consumers.

That could be as small as:

- a dedicated module that exposes known loader template names
- a helper that returns template text or a resource handle by logical name
- package-level exports for the commonly used loader templates

The important design point is that loader templates should be addressable as package resources on
purpose, not as incidental files that happen to be bundled in the wheel.

The implementation work should also consider whether the migration skill needs explicit
instructions for locating these templates in installed-package environments. If the skill currently
assumes source-tree-relative access patterns, that guidance may need to be updated alongside the
package interface so migration flows keep working consistently.

## Scope Boundaries

- This does not require exposing every template file in the package as top-level API.
- This is specifically about loader templates and adjacent authoring templates that should be part
  of the supported interface.
- This should not duplicate large amounts of command logic in the template API.

## Design Questions

- Should the supported interface return template text, `importlib.resources` handles, or both?
- Should the exported names be individual constants/helpers, or one registry-style lookup API?
- Which templates count as public API: only loader templates, or also definition/explainer
  templates?
- Should command code be refactored to consume the new public template API so there is only one
  access path?
- Should the migration skill gain explicit instructions about how to find loader templates through
  the supported package interface rather than by source-layout assumptions?
