# Workflow Parse Error Handling

## Summary

Malformed workflow YAML should produce a clean CLI error, not a Python traceback. The current
workflow loading path allows YAML parser exceptions to escape the `myteam start` command's intended
error handling.

## Problem

`load_workflow(...)` relies on `yaml.safe_load(...)`, which can raise YAML-specific parser or
scanner exceptions for malformed files. The `start` command currently catches `OSError` and
`ValueError`, but not YAML parse exceptions.

That means an invalid workflow file can crash through the CLI with an implementation traceback
instead of a normal user-facing failure message.

This is a poor interface for authors because:

- malformed input is an expected user error, not an internal crash
- the traceback leaks implementation detail instead of explaining the authored problem
- the current behavior contradicts the documented contract for malformed workflow failures

## Goals

- Ensure malformed workflow files fail with a clean, consistent CLI error message.
- Keep YAML/parser internals out of the normal user experience.
- Preserve useful error detail without exposing a raw traceback.

## Proposed Change

Normalize workflow parse failures into the same command-level error path as other load failures.

Reasonable implementation approaches include:

- catching `yaml.YAMLError` inside `load_workflow(...)` and re-raising as `ValueError`
- or expanding the `start` command's error handling to catch YAML parse exceptions explicitly

The change should include:

- one clear, user-oriented parse failure message
- CLI-flow coverage for malformed YAML that currently escapes as a traceback
- a quick pass over docs to ensure the failure contract is described consistently

## Scope Boundaries

- This item is about command-level handling for invalid YAML, not richer schema diagnostics.
- This does not require line-by-line authoring hints beyond whatever PyYAML already exposes.
- This does not require changing the authored workflow format itself.

## Open Questions

- Should parse failures be normalized in the parser layer or at the CLI boundary?
- How much of the underlying YAML error detail should be preserved in the final message?
- Should malformed YAML be distinguished from semantic validation failures in the printed text?
