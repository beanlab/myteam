# Test Proposal

## Summary

Add a `pytest` suite that treats `myteam` as a command-line tool 
and verifies interface behavior rather than internal implementation.

The goal is not to lock down helper function structure. 
The goal is to capture the user-visible contract:

- which commands succeed or fail
- what they print
- what files and directories they create, modify, or remove
- what a loaded role or skill exposes to the next agent

Tests should run `myteam` in an isolated temporary project and assert on the final state.

## Testing Philosophy

Prefer high-level use cases over unit tests of internal helpers.

Good tests for this repo:

- create a temporary working directory
- run `myteam ...` commands there
- inspect stdout, stderr, exit status, and filesystem results

Avoid tests that primarily assert:

- which private helper function was called
- how many internal functions exist
- the exact decomposition of a module
- incidental implementation details that could change during refactoring without changing behavior

The suite should document what `myteam` does, not how it happens to be written today.

## Recommended Test Layout

Create:

```text
tests/
  conftest.py
  test_init_flow.py
  test_role_and_skill_creation.py
  test_loading_flow.py
  test_remove_flow.py
  test_download_flow.py
  test_version_and_list_flow.py
```

This structure is organized around user workflows rather than source modules.

## Test Harness Approach

The core test fixture should create an isolated temp project directory and run commands from there.

Recommended approach:

- use `tmp_path` to create a clean repo-like workspace
- invoke the CLI in subprocess form, for example `python -m myteam ...` or `myteam ...`
- set `cwd` to the temp project
- assert on:
  - exit code
  - stdout/stderr
  - resulting files and file contents

This gives better protection against regressions in command wiring, path handling, template use, 
and loader execution than direct function-level tests.

## Proposed Coverage

### `tests/conftest.py`

Provide a small set of helpers:

- `run_myteam(tmp_path, *args)` to execute the CLI in a temp directory
- a helper to read files relative to the temp project
- optional helpers to create fake remote responses for download tests

Keep helpers minimal. They should support scenario tests, not replace them.

### `tests/test_init_flow.py`

Cover the initialization experience end to end.

Scenarios:

- `myteam init` in an empty directory creates:
  - `AGENTS.md`
  - `.myteam/role.md`
  - `.myteam/load.py`
- `myteam init` leaves an existing `AGENTS.md` untouched
- after `myteam init`, `myteam get role` succeeds and prints the root role plus built-in discovery guidance

Assertions should focus on created files, key output text, and success status.

### `tests/test_role_and_skill_creation.py`

Cover authoring flows as the interface presents them.

Scenarios:

- `myteam new role developer` creates `.myteam/developer/role.md` and `.myteam/developer/load.py`
- `myteam new skill python` creates `.myteam/python/skill.md` and `.myteam/python/load.py`
- nested creation works:
  - `myteam new role engineering/frontend`
  - `myteam new skill python/testing`
- creating an already existing role or skill fails with a useful message and a non-zero exit code

Assertions should check directory structure and user-visible errors, not the internals of `new_dir()`.

### `tests/test_loading_flow.py`

This should be the most important part of the suite because loading roles and skills is the core product behavior.

Scenarios:

- `myteam get role` loads the root role from `.myteam/`
- `myteam get role developer` loads the requested child role
- `myteam get skill python/testing` loads the requested nested skill
- role loading strips YAML frontmatter before printing instructions
- skill loading strips YAML frontmatter before printing instructions
- loading a role lists immediate child roles, skills, and Python tools beneath that node
- loading a skill lists immediate child skills and tools beneath that node
- uppercase definition files are accepted:
  - `ROLE.md`
  - `SKILL.md`
- requesting a missing role fails clearly
- requesting a missing skill fails clearly
- requesting a path that exists but is not a valid role or skill fails clearly

These tests should assert the observable loader behavior from an agent’s perspective:

- what instructions are shown
- whether frontmatter is hidden
- what discoverable children are listed

### `tests/test_remove_flow.py`

Cover deletion from the interface point of view.

Scenarios:

- removing an existing role directory succeeds and deletes it
- removing a missing path fails clearly
- removing a non-directory path fails clearly
- removing an existing skill should succeed as part of the public contract

This last case is especially important because the current implementation appears suspicious for skills. 
A black-box test here is valuable because it captures expected CLI behavior regardless of how removal is implemented.

### `tests/test_download_flow.py`

Cover roster download as a command behavior, 
but keep it hermetic by mocking network access at the process boundary used by the command.

Scenarios:

- `myteam list` prints available roster names from a mocked remote tree
- `myteam download <roster>` downloads a roster directory into `.myteam/`
- downloading a single-file roster places the file at the expected destination
- downloading a tree roster preserves relative paths
- requesting a missing roster fails with a helpful list of available rosters
- invalid `repo` values fail with a useful message
- download failures from the remote source fail clearly

The assertions should be:

- printed output
- exit code
- downloaded files on disk

Do not make live network calls in the test suite.

### `tests/test_version_and_list_flow.py`

Cover the remaining public CLI surface.

Scenarios:

- `myteam --version` prints the app name and version
- `myteam list` succeeds with mocked remote data
- command wiring remains usable through the real CLI entry point

These are small tests, but they validate top-level contract stability.

## What Not To Prioritize

Do not start by writing direct tests for:

- `ensure_dir()`
- `write_py_script()`
- `_parse_yaml_frontmatter()`
- `_collect_tree_entries()`
- other private helpers

Those may still deserve direct tests later if a specific bug proves hard to capture through CLI behavior, but they should not define the initial strategy.

If a behavior can be tested through `myteam init`, `myteam new`, `myteam get`, `myteam remove`, `myteam list`, or `myteam download`, prefer that route.

## Dependencies To Add With `uv`

Minimum:

```bash
uv add --group dev pytest
```

Recommended:

```bash
uv add --group dev pytest pytest-cov
```

Rationale:

- `pytest` is the test runner
- `pytest-cov` is still useful even for higher-level tests because it helps show which public behaviors are not yet exercised

Probably not needed yet:

- `pytest-mock`: `monkeypatch` and simple fixtures should be enough
- HTTP mocking libraries: direct monkeypatching of the download layer is likely sufficient for this repo
- `pytest-xdist`: the suite should remain small and fast

## Suggested `pyproject.toml` Changes

Add basic pytest discovery config:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
```

If `pytest-cov` is added, document a coverage-oriented command such as:

```bash
uv run pytest --cov=myteam --cov-report=term-missing
```

Coverage should be treated as a visibility tool, not the primary goal. The main goal is meaningful interface-level scenarios.

## Suggested Implementation Order

1. Add `pytest` and `pytest-cov` as dev dependencies with `uv`.
2. Build a small CLI test harness in `tests/conftest.py`.
3. Add end-to-end local filesystem tests for `init`, `new`, `get`, and `remove`.
4. Add hermetic mocked-network tests for `list` and `download`.
5. Add a short README section documenting how to run tests.

## Changes Needed In `.myteam/conclude-feature`

The current skill should be updated so that once this repo has tests, feature work is concluded by validating behavior through the public interface, not just by adding unit tests.

The skill should add a dedicated testing section with requirements like:

- If code changed, add or update automated tests that cover the affected user-visible behavior.
- Prefer high-level tests that run the repo through its real command interface and assert on outputs and final state.
- Run the repo test command before concluding the feature.
- Do not proceed until tests pass, unless the user explicitly accepts a known failure.
- If no tests were added for a code change, explain why.

Suggested command text for this repo:

```md
### Run tests

If code has changed, add or update automated tests that cover the affected public behavior.

Prefer tests that exercise the real interface of the project and assert on observable outcomes.

Run `uv run pytest`.

If the project uses coverage checks for the current branch, run the documented coverage command instead.

Do not proceed until tests pass, unless the user explicitly approves proceeding with a known failure or the change is documentation-only.

If you were unable to add tests for a code change, explain the gap clearly in your final report.
```

The skill should also be corrected to refer to `pyproject.toml`, not `project.toml`.

## New `.myteam` Skill For Test Philosophy

The testing philosophy in this document should also be captured in a dedicated `.myteam` skill so agents working in this repo are instructed to write the right kinds of tests.

That skill should explain:

- tests should focus on public interface behavior rather than internal implementation details
- tests should prefer high-level use cases that run real `myteam` commands in an isolated environment
- assertions should focus on observable results such as exit status, output, and final filesystem state
- private helper tests are secondary and should only be added when a behavior is hard to capture through the interface
- new behavior should be traced back to the interface contract in `design/interface.md`
- tests should act as evidence that the documented interface works as intended

The skill should be loaded whenever an agent is adding or modifying tests in this repo.

## Notes

- A black-box test for skill removal is likely to expose whether `myteam remove <skill>` currently behaves correctly.
- The initial suite should stay offline, deterministic, and fast enough to run during normal feature work.
- If some behavior turns out to be awkward to test purely through subprocess execution, a secondary approach is acceptable: call the public command function while still asserting only on externally visible behavior. The behavioral contract should remain the focus.
