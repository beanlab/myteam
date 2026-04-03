# Update Downloaded Content

## Framework Refactor

Refactor roster installation code so `download` and `update` both use the same managed-install
primitive.

Specific changes:

- Introduce a helper that resolves and validates managed source metadata from a subtree root.
- Introduce a helper that installs a roster tree into a destination using one shared flow:
  fetch roster entry, require a tree roster, fetch subtree files, download files, and write
  `.source.yml`.
- Split destination handling into two modes:
  one for fresh installs that rejects existing content, and one for managed updates that replaces only
  the targeted managed subtree.
- Add helpers to discover managed subtree roots by scanning `.myteam/` for `.source.yml` files.
- Keep the existing roster fetch/download functions as the network primitive; do not change role/skill
  loading behavior.

Why this refactor:

- `update` is conceptually the same install operation as `download`, but with provenance-derived inputs.
- Sharing one install path keeps metadata writing, roster validation, and file placement consistent.
- The refactor isolates overwrite behavior from network behavior so later checksum work can add dirty
  detection without reworking fetch logic again.

The existing tests should continue to pass after this refactor, because no user-visible behavior changes
until the new command is wired in.

## Feature Addition

Add a new CLI command, `myteam update [path]`, with provenance-driven replacement semantics.

Specific behavior:

- `myteam update <path>`:
  resolve the target as either the provided path or `.myteam/<path>` relative to the project root, then
  require `.source.yml` at that subtree root.
- `myteam update`:
  recursively scan `.myteam/` for `.source.yml` files and update each discovered managed subtree root.
- For each target:
  read `repo`, `roster`, and `ref` from `.source.yml`, then re-install that roster into the same local
  subtree root.
- Replacement semantics:
  remove the existing managed subtree root and recreate it from the remote source, then write fresh
  metadata.
- Error handling:
  fail clearly for missing metadata, invalid metadata, missing `.myteam/`, no managed installs found,
  invalid remote repo, missing remote roster, or file-roster targets.

Test coverage to add:

- update of one managed subtree refreshes files and rewrites metadata
- update with explicit `.myteam/...` path works
- update with bare relative path under `.myteam/` works
- update with no path refreshes multiple managed subtrees
- update fails when the target is not a managed subtree
- update fails when no managed installs exist
- update fails when metadata is incomplete

Out of scope for this branch:

- checksum or manifest tracking
- dirty local-edit detection
- force overwrite or merge workflows
- trust verification changes
