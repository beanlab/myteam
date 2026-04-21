# Workflow Validation And Agent Coverage

## Summary

Several public workflow authoring and routing behaviors are implemented but not yet covered well in
tests. Those gaps are small individually, but together they leave meaningful room for regression in
user-facing validation and agent selection behavior.

## Problem

The workflow parser and executor enforce several public rules:

- workflow files must have the expected top-level shape
- step names must be valid identifiers
- required fields must exist and have the right types
- step-level `agent` values must validate and route correctly

Some of these cases are covered today, but not comprehensively. In particular, the suite should do
more to protect the authoring experience around invalid files and the routing behavior around
explicit per-step agent selection.

This matters because:

- validation behavior is part of the public authoring interface
- gaps in invalid-shape coverage can turn into confusing runtime behavior later
- agent override behavior is a key extensibility point for workflows

## Goals

- Broaden test coverage for documented workflow validation rules.
- Add explicit coverage for successful per-step `agent:` override behavior.
- Make the test suite reflect the full public authoring contract, not only a subset of it.

## Proposed Change

Add targeted tests for at least these cases:

- top-level YAML value is not a mapping
- invalid step names
- missing required `prompt` or `output`
- non-string `prompt`
- non-string `agent`
- successful step execution using an authored `agent:` override instead of the default agent

These can stay as focused unit or flow tests as appropriate, as long as they protect the public
behavior and not just internal implementation details.

## Scope Boundaries

- This item is about missing validation and routing coverage, not new workflow features.
- This does not require supporting additional agent types yet.
- This does not require broad schema tooling beyond the current parser approach.

## Open Questions

- Which of these cases belong in parser unit tests versus command-level flow tests?
- Should successful authored-agent coverage remain at the executor level, or also appear in a
  higher-level integration test?
- Are there additional documented validation rules that should be enumerated in one place before
  expanding the suite further?
