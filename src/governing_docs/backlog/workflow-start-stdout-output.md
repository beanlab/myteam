# Workflow Start Stdout Output

## Summary

`myteam start` should expose a successful workflow's final structured result on standard output.
The current implementation completes successfully without printing the workflow output, which makes
the command hard to consume directly and contradicts the documented application interface.

## Problem

The documented interface says workflow execution should emit runtime output on standard output.
Today the success path only logs lifecycle information when `--verbose` is enabled and otherwise
returns with no user-visible result payload.

That creates several problems:

- successful workflows are not directly useful to shell callers or wrappers
- the interface documentation and the implementation disagree
- tests currently normalize this behavior by asserting empty `stdout` on success

## Goals

- Make successful `myteam start` runs print the workflow result in a stable user-visible format.
- Align the implementation, tests, and governing docs around the same contract.
- Preserve clear separation between workflow result output and error reporting.

## Proposed Change

Update the `start` command success path so it renders `WorkflowRunResult.output` to standard output.

The output format should be explicit and stable enough for both humans and simple tooling. A likely
baseline is YAML or JSON emitted once after the workflow completes successfully.

The work should include:

- deciding and documenting the success-output format
- implementing success-path rendering in `commands.py` or a narrow workflow-output helper
- updating CLI-flow tests to assert the intended output instead of empty `stdout`
- confirming that verbose lifecycle logs remain on standard error

## Scope Boundaries

- This item is about the final command output contract, not a broader redesign of workflow logging.
- This does not require streaming per-step structured results during execution.
- This does not require a new machine-oriented flag unless the chosen format proves insufficient.

## Open Questions

- Should the success payload be emitted as YAML or JSON by default?
- Should empty workflow output render as `null`, `{}`, or nothing?
- Does the command need a future `--json` or `--yaml` flag, or is one stable default enough?
