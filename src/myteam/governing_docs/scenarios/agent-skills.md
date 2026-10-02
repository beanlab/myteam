# Packaged Agent Skills

The `src/myteam/agent_skills/` tree contains the skills shipped with `myteam` for helping agents understand and work with the application.

The governing documents and agent skills serve different purposes:

- `src/myteam/governing_docs/` is the authoritative description of how the application works. It is organized thematically for maintainers.
- `src/myteam/agent_skills/` presents relevant governing information to agents. It is organized by the role or task for which the information is needed.

The skill tree is a set of role-oriented views over the governing documents, not a second source of truth.

## Top-level skill

`using-myteam.md` is the bootstrap skill. It explains how an agent should think about and use `myteam`, then exposes folders containing more specialized guidance.

`myteam explain`, the public `explain_resources()` API, and the `myteam_explain()` Jinja helper render this skill. They must not maintain separate copies of its content.

The top-level skill should contain only guidance broadly useful to an agent using `myteam`. Detailed authoring, operating, extension, and implementation information should remain progressively discoverable through role folders.

## Role organization

Folders group skills according to the work an agent is performing, such as:

- authoring skills, workflows, and harnesses;
- operating an existing harness;
- extending `myteam` through its Python API or configuration;
- understanding `myteam` internals.

Each folder must contain a `description.md` that tells an agent when to list it. Each skill description must state when the skill should be loaded.

A governing document may support more than one role and may therefore be included by more than one skill. Conversely, one skill may compose several governing documents when the agent needs them together for a single task.

The skill hierarchy should optimize the context presented to agents. It does not need to mirror the governing-document hierarchy.

## Composing governing content

Markdown skills should use `read_file` to include governing documents rather than copying their content. Governing documents commonly contain literal Jinja examples, so they should normally be included without rendering:

```jinja2
{{ read_file('../../governing_docs/scenarios/skills.md', render=False) }}
```

Paths are relative to the skill containing the expression and must remain valid in the installed package as well as the source tree.

A skill may add concise role-specific framing around included documents. Application behavior and other shared factual content belong in the governing documents, not in that framing.

## Maintenance

When governing behavior changes:

1. Update the relevant governing document first.
2. Identify every role that needs the changed information.
3. Add, remove, split, or regroup skill views as needed.
4. Verify folder and skill descriptions still trigger at the appropriate scope.
5. Verify every skill can be listed and loaded from the packaged tree.
6. Verify `myteam explain` remains equivalent to loading `using-myteam.md`.

Avoid one wrapper per governing document by default. Create a skill when a distinct agent role or task needs the content. A one-to-one mapping is appropriate when a governing scenario already has the right scope for that task.

If a governing document repeatedly supplies too much unrelated content to a skill, split the governing document along thematic boundaries rather than duplicating or extracting fragile sections in the skill tree.
