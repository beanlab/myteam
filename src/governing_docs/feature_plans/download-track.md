# Download Tracking Feature Plan

## Framework Refactor

### Current design

`src/myteam/rosters.py` currently mixes four concerns inside one flow:

- locating a roster entry in the remote repository
- deciding whether that entry is a tree or blob
- mapping the remote entry onto a local destination path
- downloading files directly into that destination

That structure kept the initial implementation short, but it makes the new managed-install behavior
awkward because the local install root, overwrite checks, and metadata writing all need to happen as
one coherent operation.

### Refactor goal

Refactor the roster download code around an explicit managed install root.

The refactor should separate:

- remote roster resolution
- local install-path resolution
- destination validation
- file download into a managed root
- provenance metadata writing

### Planned refactor

1. Introduce helpers that compute the managed local root for a roster download.
   - Default installs should preserve the remote roster path under `.myteam/`.
   - Explicit destinations should be treated as the managed local root.
2. Introduce a helper that validates the roster entry type before download begins.
   - Tree rosters remain supported.
   - Blob rosters fail immediately with a clear error.
3. Introduce a helper that validates the target path before any files are written.
   - If the target path does not exist, the install may proceed.
   - If the target path exists and contains a matching `.source.yml`, fail with guidance to run
     `myteam update <path>`.
   - If the target path exists without matching managed-source metadata, fail with guidance to delete
     the destination or choose a different path.
4. Introduce a helper that writes `.source.yml` from structured metadata after file download succeeds.
   - Use the existing YAML dependency already present in the project.
5. Keep the network fetch primitive centered on the existing `_fetch_json` and `_download_file`
   helpers so the refactor stays local to roster install orchestration.

### Why this framework change is sufficient

Once install-root resolution and destination validation are explicit, the feature itself becomes
simple:

- download tree files into one managed root
- write `.source.yml`
- reject unsupported or conflicting targets before any write occurs

That keeps the business behavior small and avoids spreading provenance logic into unrelated command
code.

## Feature Addition

### Behavior to implement

Implement managed folder downloads for `myteam download` with the following behavior:

1. `myteam download <roster>`
   - resolves `<roster>` as a folder roster only
   - installs it under `.myteam/<roster>/`
   - writes `.source.yml` at `.myteam/<roster>/.source.yml`
2. `myteam download <roster> <destination>`
   - resolves `<roster>` as a folder roster only
   - installs the roster contents into the explicit destination path under `.myteam/`
   - writes `.source.yml` at the explicit destination root
3. If the remote roster is a blob, fail with a clear folder-only error.
4. If the destination already exists and belongs to the same recorded source, fail with guidance to
   run `myteam update <path>`.
5. If the destination already exists and is unrelated content, fail with guidance to delete it or
   choose a different destination.

### `.source.yml` contents for this feature

This feature should record source-tracking metadata only. Checksum fields are intentionally deferred to
 backlog work.

The metadata should include:

- source repo identifier
- source roster path
- source ref used for download
- local install path
- download timestamp

### Test updates anticipated by this plan

`tests/test_download_flow.py` should be updated to verify:

- default tree installs preserve the roster folder path under `.myteam/`
- explicit destination installs write into the provided managed root
- `.source.yml` is created at the managed root
- blob rosters fail with the new folder-only error
- same-source existing installs fail with `myteam update <path>` guidance
- unrelated existing destinations fail with delete-or-relocate guidance

The tests should continue using the high-level CLI harness and monkeypatched roster fetch/download
helpers so behavior is asserted through command outcomes and final filesystem state.
