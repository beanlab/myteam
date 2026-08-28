# Improve skill and workflow authoring documentation

## Problem

Authors do not have one clear path to the features available when composing skills and workflows:

- `.agents/dev/skills/authoring-workflows.md` does not explain `increase_headers`.
- `myteam explain` does not mention `increase_headers` or direct authors to its existing Jinja documentation.
- There is no authoring-skills document corresponding to the workflow-authoring guidance.

Although `src/governing_docs/scenarios/jinja-support.md` documents `increase_headers`, authors are unlikely to discover it from the guidance they receive while creating resources.

## Proposal

1. Add concise `increase_headers` guidance and examples to the workflow-authoring document, including callable and filter forms for safely embedding Markdown fragments beneath surrounding headings.
2. Update `myteam explain` to expose or link to the available authoring/Jinja features, including `increase_headers`.
3. Add an authoring-skills document covering skill structure, discoverability, descriptions, dynamic skill content, Jinja helpers, relative path resolution, and when to use `increase_headers`.
4. Cross-reference the skill- and workflow-authoring documents and the canonical Jinja-support documentation rather than duplicating detailed behavior.

## Acceptance criteria

- An agent following the workflow-authoring guidance can discover and correctly use `increase_headers`.
- An agent receiving `myteam explain` can discover where authoring helpers are documented.
- Skill authors have dedicated authoring guidance comparable to workflow authors.
- Examples demonstrate embedding Markdown without heading-level conflicts.
