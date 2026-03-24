# Roster Architecture Cleanup

## Summary

The current roster implementation works for the tested happy path, but its data model is underspecified and a few behaviors are coupled to GitHub assumptions rather than to a clear `myteam` contract.

This backlog item covers tightening the roster abstraction so `myteam list` and `myteam download` behave predictably across repositories and preserve structure correctly on disk.

## Problems

### Default branch assumption

The implementation currently hard-codes `main` when building both API and raw-content URLs.

That creates an unnecessary compatibility failure for repositories whose default branch is not `main`.

### Loose roster discovery model

`myteam list` currently prints every path returned from the recursive GitHub tree response.

That means the command exposes:

- top-level directories
- nested directories
- standalone files
- nested files

as if they are all first-class rosters.

This is not a clean abstraction. A roster should have a defined install unit and discoverability rule.

### Blob downloads lose structural intent

Single-file roster downloads currently write to `destination / basename(path)`.

That means a remote path such as `nested/example.md` is installed as `example.md`, which discards the remote path and can collide with other file names.

### GitHub-specific API shape is embedded directly into command behavior

The current implementation mixes:

- repository validation
- GitHub URL construction
- tree traversal
- user-facing CLI behavior
- file installation

inside one small module.

The code is still readable, but the design boundary is thin enough that future features such as provenance tracking or alternate repository layouts will be awkward to add cleanly.

## Goals

- Define what a roster is in user-facing terms.
- Make listing and download behavior match that definition.
- Support repositories regardless of whether the default branch is `main`.
- Preserve downloaded file structure exactly unless an explicit normalization rule exists.
- Keep the fetch logic simple enough to remain testable without network access.

## Proposed Direction

### Define roster install units explicitly

Pick one of these models and document it clearly:

- only top-level directories are rosters
- top-level directories plus top-level files are rosters
- rosters are declared by metadata rather than inferred from arbitrary tree paths

The simplest near-term option is:

- top-level directories are downloadable roster trees
- top-level files are downloadable single-file rosters
- nested paths are implementation details, not roster names surfaced by `list`

### Separate repository resolution from installation

Split the roster flow into clearer responsibilities:

- resolve repository metadata, including default branch or ref
- enumerate available roster install units
- resolve a selected roster into file entries
- install those file entries into a destination

This would make the code easier to reason about and reduce the amount of GitHub-specific branching in user-facing command functions.

### Preserve remote-relative paths on install

Downloaded content should preserve its remote-relative path within the selected roster unit.

For tree rosters, that is already the intended behavior.

For single-file rosters, install the file using the selected roster path rather than only its basename.

### Prepare for provenance-aware downloads

Any roster cleanup should keep the future `download` plus `update` design in mind.

In practice that means the roster layer should expose a stable concept of:

- source repo
- source ref
- roster name
- included file paths

without mixing those details into ad hoc printing logic.

## Scope Boundaries

- This backlog item is about roster definition and download behavior, not trust or update policy.
- This does not require support for non-GitHub remotes yet.
- This does not require a complete rewrite of the roster feature if a narrow refactor can establish clean boundaries.

## Open Questions

- Should `myteam list` show only installable top-level roster names, or should it have a verbose mode for deeper inspection?
- Should a downloaded single-file roster preserve any parent path components, or should single-file rosters be restricted to top-level files only?
- Should the CLI accept an explicit `--ref` override before default-branch discovery is introduced as the default behavior?
