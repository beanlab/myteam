# Feature Plan: Interface Document And Initial Test Harness

## Goal

Create the first `src/governing_docs/application_interface.md` document and the initial automated
test suite that validates the public CLI contract.

## Desired Outcome

- [x] Review the current public CLI surface in `README.md` and `src/myteam/`.
- [x] Describe the intent of `myteam` from a user-facing perspective.
- [x] Document each supported command as a black-box interface.
- [x] State the observable outcome of each command, including filesystem changes and printed output at a high level.
- [x] Keep the document implementation-aware enough to match the current app behavior, but avoid internal design detail that would not matter to a CLI user.
- [x] Review the test-design notes in `design/tests.md`.
- [ ] Add a pytest-based harness for isolated CLI workflow tests.
- [ ] Cover the core public flows: `init`, `new`, `get`, `remove`, `list`, `download`, and `--version`.
- [ ] Keep assertions focused on exit status, output, and final filesystem state.

## Non-Goals

- [ ] Change command behavior.
- [ ] Redesign the command set.
- [ ] Document internal helper functions or module layout.
- [ ] Replace every future need for lower-level tests.

## Strategy

Use the README as the current product narrative and confirm command behavior against the actual CLI
wiring in `src/myteam/cli.py` and command implementations in `src/myteam/commands.py`,
`src/myteam/rosters.py`, and related utilities.

The interface document should emphasize:

1. What `myteam` is for.
2. What assumptions it makes about `.myteam/`.
3. What each command accepts.
4. What a user or agent can expect to happen after each command succeeds.
5. What broad error outcomes matter at the interface level.

The test suite should follow `design/tests.md` and `testing-philosophy`:

1. Run the application through its public CLI entry point whenever practical.
2. Use isolated temporary directories as project roots.
3. Assert on observable output and filesystem state.
4. Use hermetic mocking for roster-network behavior.
5. Organize tests by workflow rather than source module.

## Notes

This branch now includes both documentation and test-harness work.
It should not require framework changes.
If code changes are limited to tests and test configuration, no public-interface version bump should
be necessary.
