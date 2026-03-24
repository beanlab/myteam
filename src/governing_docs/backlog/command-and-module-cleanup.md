# Command and Module Cleanup

## Summary

Most of the package is small and coherent, but a few implementation choices now depend on implicit control flow or convenience-based module boundaries rather than clear interfaces.

This backlog item covers the non-roster cleanup work needed to keep the architecture simple as the package grows.

## Problems

### Command flow depends on `SystemExit` as control flow

`get_name()` executes a `load.py` and then raises `SystemExit(result.returncode)`.

That works in the CLI, but it also means callers rely on process termination as the success path. In particular, `get_skill()` depends on that behavior to avoid falling through into its final "Not a skill" error branch.

This is functional, but it is workaround-shaped and makes the command layer less reusable and less obvious.

### `remove()` relies on accidental path symmetry

`remove()` currently resolves its target through a role-oriented helper and carries a `TODO` noting that skills are not handled explicitly.

The command happens to work because roles and skills currently live in the same directory tree.

That is an implicit assumption rather than a clear command model.

### `utils.py` is accumulating unrelated responsibilities

`utils.py` now contains:

- root discovery
- environment-based path override behavior
- instruction printing
- YAML frontmatter parsing
- builtin skill path resolution
- directory listing and info formatting
- git-ignore-aware tree rendering
- explainer template printing

For the current code size this is still manageable, but it is the clearest place where the architecture is trending toward a grab-bag module.

### Minor duplication of path-related concerns

Some path constants and helpers live in `paths.py`, while adjacent path logic remains in other modules or local helpers.

This is not a defect by itself, but it suggests the codebase has not fully decided whether it wants a centralized path model or lightweight local path handling.

## Goals

- Make command behavior readable without depending on hidden process-exit side effects.
- Define removal semantics explicitly for loadable nodes.
- Keep modules cohesive enough that future features have obvious homes.
- Preserve the current simplicity of the package rather than introducing unnecessary abstraction.

## Proposed Direction

### Make loader execution return a result instead of exiting directly

Refactor the command path so one function is responsible for:

- validating the requested node
- executing its `load.py`
- returning an exit status

Then let the outer CLI command decide whether to return normally or raise `SystemExit`.

The key design goal is that "found and executed" should be visible in normal control flow rather than encoded as an exception path.

### Introduce a node-path concept for commands that target `.myteam/`

Commands such as `remove` should operate on a generic "node path inside the project tree" rather than pretending the target is role-specific.

That can remain a very small helper if the package wants to avoid a heavier object model.

### Split `utils.py` by responsibility when the next feature touches it

A full reorganization is not required immediately, but future edits should use a cleaner seam. A reasonable split would be:

- `discovery` or `listing` helpers
- instruction/frontmatter helpers
- tree-rendering helpers
- builtin-skill resolution helpers

The point is not to maximize module count. The point is to avoid one file becoming the default home for unrelated behavior.

### Normalize error-handling style

The code currently mixes:

- printing then `raise SystemExit(1)`
- printing then `exit(1)`
- returning strings for some CLI commands

That should be made more consistent so the command layer is easier to audit and test.

## Scope Boundaries

- This backlog item is not asking for a framework-heavy command architecture.
- This does not require changing the user-visible CLI surface unless a cleanup exposes a real inconsistency worth fixing.
- This does not require moving every helper out of `utils.py` immediately.

## Open Questions

- Should command functions continue to own stderr printing, or should they raise typed exceptions that the CLI layer renders?
- Is it worth introducing a small internal "loadable node" helper for roles and skills, or is a few focused helper functions enough?
- Which pieces of `utils.py` are most likely to grow next and therefore most worth extracting first?
