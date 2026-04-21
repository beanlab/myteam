# Workflow End-to-End Interface Tests

## Summary

The new workflow test suite has good internal unit coverage, but it still lacks a strong black-box
test of the authored workflow experience. The public value of workflows is the end-to-end CLI
contract, so the suite should exercise that contract directly.

## Problem

Current workflow tests are layered, but heavily stubbed:

- CLI-flow tests stub both workflow loading and execution
- engine tests stub the step executor
- step-executor tests stub PTY execution

That structure is useful for focused unit tests, but it leaves a gap: the actual path from authored
YAML to ordered execution to reference passing to final command output is not tested end to end.

As a result:

- interface regressions can slip through even when all workflow tests pass
- the suite is weaker on the user experience than on implementation mechanics
- command-level documentation is not validated against the real runtime path

## Goals

- Add at least one deterministic black-box workflow test that exercises the real workflow stack.
- Validate the authored user experience rather than only internal function behavior.
- Catch regressions in CLI-visible output, step ordering, and inter-step data flow.

## Proposed Change

Add an integration-style workflow test that uses:

- a real authored workflow YAML file
- a deterministic local fake agent process
- the actual parser, engine, executor, and command path

The scenario should cover a representative happy path:

- step 1 produces structured output
- step 2 consumes that output through a workflow reference
- the workflow completes in authored order
- the command emits the expected final result and uses the expected error/output channels

If practical, add one similarly black-box failing scenario for a representative step failure.

## Scope Boundaries

- This item is about interface-confidence coverage, not replacing the current unit tests.
- The fake agent should stay deterministic and local; this does not require invoking a real external
  interactive coding agent in CI.
- This does not require broad snapshot testing of all workflow transcripts.

## Open Questions

- Should the fake agent be implemented as a reusable helper under `tests/helpers/`?
- What final-output format should the integration test assert once the CLI output contract is fixed?
- Is one happy-path integration test enough initially, or should one failure-path test land at the
  same time?
