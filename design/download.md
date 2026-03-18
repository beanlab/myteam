# Download Provenance and Update Design

## Summary

Keep `myteam` runtime loading local-only. Extend `myteam download` so downloaded content carries source metadata, then add `myteam update [path]` to re-fetch installed content from its recorded origin.

This preserves the current `get role` / `get skill` model and avoids turning role or skill loading into a networked operation.

## Goals

- Keep `get role` and `get skill` deterministic and filesystem-based.
- Make downloaded remote content updateable without requiring the user to re-specify its origin.
- Support multiple independently downloaded subtrees inside `.myteam/`.
- Protect local edits from accidental overwrite during update.

## Proposed Behavior

### `myteam download`

Treat `download` as an install operation instead of a one-shot copy.

When content is downloaded, write a hidden metadata file at the root of the installed subtree. A placeholder name like `.myteam-source.yml` is sufficient for design purposes.

The metadata should record:

- source repo identifier
- source roster or subtree path within the remote repo
- source ref or branch used for the download
- local install destination
- download timestamp
- optional remote tree SHA or similar fingerprint

### `myteam update [path]`

Add an `update` command that uses stored metadata to re-download installed remote content.

Behavior:

- `myteam update <path>` updates the specified installed subtree
- `myteam update` scans `.myteam/` for subtree metadata files and updates all downloaded subtrees
- update fails by default if local managed files were modified after download
- a force option should allow replacing locally modified managed files

## Scope Boundaries

- `get role` and `get skill` should remain unchanged
- remote content should not be fetched dynamically during role or skill loading
- this design does not yet define trust verification for downloaded content
- this design does not yet define an interactive merge strategy for dirty local copies

## Implementation Notes

- The existing roster download logic in `src/myteam/rosters.py` should remain the fetch primitive.
- Download code should be refactored so install metadata is written as part of the same operation that places files on disk.
- Update should resolve a target subtree by locating its metadata file rather than inferring provenance from directory naming alone.
- Dirty detection should compare the current managed subtree against the last installed state strongly enough to block accidental overwrite. The exact mechanism can be finalized during implementation.

## Open Follow-Up Work

- Design and implement a trust framework for verifying and tracking trusted content.
- Design and implement a merge-assist skill for updating dirty local copies.
