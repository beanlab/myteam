# Nested Download Metadata Warning

## Summary

When `myteam download` or `myteam update` installs a managed subtree, the downloaded content may
itself contain one or more `.source.yml` files from prior managed downloads.

That creates nested provenance inside the installed tree. Even before the trust framework is fully
implemented, `myteam` should detect this condition and warn the caller so they know the downloaded
content contains additional remotely sourced material.

## Problem

The current managed-download model treats the installed subtree root as one provenance unit.

That can hide an important detail:

- the downloaded roster may itself vendor other managed downloaded content
- nested `.source.yml` files may point at other repositories or sources
- a user may reasonably assume one remote source when the installed tree actually carries multiple
  provenance layers

This is especially relevant for future update and trust work, because nested managed roots may need
different handling from ordinary files.

## Goals

- Detect nested `.source.yml` files inside downloaded or updated managed content.
- Warn the caller when nested managed-source metadata is present.
- Surface enough path information for the caller to inspect the nested managed content.
- Preserve the current simple download/update flow while making hidden provenance visible.

## Non-Goals

- Blocking installs purely because nested metadata is present.
- Defining the full trust or verification policy for nested managed content.
- Defining recursive update semantics for nested managed roots.

## Proposed Behavior

After `myteam download` or `myteam update` finishes writing the managed subtree:

- scan the installed subtree for `.source.yml` files below the managed root
- ignore the root `.source.yml` that belongs to the current managed install
- if nested metadata files are found, print a warning on standard error

The warning should explain:

- that nested managed-source metadata was found
- that the installed content includes additional downloaded provenance
- which nested paths were detected, or at least the first few plus a count if there are many

## Implementation Notes

- Detection should happen after installation so the warning reflects the actual on-disk result.
- The scan should be rooted at the managed install destination and exclude the root metadata file.
- This feature should remain warning-only until trust and recursive update behavior are designed.

## Open Follow-Up Work

- Decide whether nested managed metadata should affect trust verification state.
- Decide whether `myteam update` should skip, recurse into, or explicitly reject nested managed roots.
- Decide whether `download` or `update` should eventually require an explicit user acknowledgement for
  nested remote provenance.
