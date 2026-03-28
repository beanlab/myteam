# Download Checksum Tracking

## Summary

Extend managed download metadata so each installed subtree records a checksum of the original
downloaded content, then use that checksum in future update flows to detect local modifications before
overwriting managed files.

This work is intentionally separate from the initial download-tracking feature. The first feature only
records origin metadata in `.source.yml`; checksum recording and checksum-based decisions belong to
this later feature.

## Goals

- Detect whether a managed downloaded subtree still matches the content originally installed.
- Let future `myteam update` behavior distinguish "same source, unchanged local content" from
  "same source, locally modified content."
- Reuse the existing migration-style safety model: block risky replacement by default and direct the
  caller through an explicit next step instead of silently overwriting.

## Proposed Behavior

### Metadata

`.source.yml` should include a checksum that represents the original downloaded content for the managed
subtree.

The checksum should be stable across platforms and based on the downloaded file set and their contents,
not incidental filesystem metadata.

### `myteam update`

Before replacing files in a managed subtree, `update` should compare the current local subtree against
the original checksum recorded in `.source.yml`.

Outcomes:

- if the current local checksum matches the recorded original checksum, the subtree is clean and may be
  updated normally
- if the checksum differs, `update` should treat the subtree as locally modified and stop before
  overwriting it
- the user-facing failure should explain that the managed content has local changes and that a separate
  guided resolution flow is required

## Scope Boundaries

- This document does not define the final merge or conflict-resolution interface for dirty managed
  trees.
- This document does not define trust verification for downloaded content.
- This document does not require `download` itself to compare current content against the checksum;
  that behavior belongs to the future update workflow.

## Implementation Notes

- The checksum should be computed from a canonical traversal of the managed subtree.
- The checksum format should be straightforward to recompute during future update and migration flows.
- The eventual dirty-content handling should align with the existing migration philosophy: clear
  explanation, no silent overwrite, explicit operator action required.

## Open Follow-Up Work

- Design the exact checksum algorithm and canonical file-ordering rules.
- Define the user workflow for resolving dirty managed subtrees during `myteam update`.
- Decide whether a future force option should exist, and if so, how it should be gated.
