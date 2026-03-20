# Feature Plan: `.myteam` Migration Guidance

## Goal

Add a safe upgrade-guidance flow for existing `.myteam/` trees so projects created by older
`myteam` releases can discover newer features, inspect the relevant migration instructions, and let
an agent propose project-specific edits instead of blindly applying a generic migration command.

## Desired Outcome

- [x] Keep using the current `migration-command` branch for this work.
- [x] Define a persistent version marker inside `.myteam/`.
- [x] Ensure `myteam init` writes the current `myteam` version into a newly created `.myteam/`.
- [x] Ensure `myteam init` includes built-in upgrade-related skills under the generated `.myteam/` tree.
- [x] Update the default root role loader so it warns when the installed `myteam` version is newer than the stored `.myteam` version.
- [x] Provide a built-in skill that exposes migration guidance derived from the packaged migration documents.
- [x] Provide a built-in skill that exposes changelog entries newer than the stored `.myteam` version.
- [x] Remove the `myteam migrate` CLI command and any command-oriented migration behavior.
- [x] Add high-level tests that exercise the init and built-in upgrade-skill flows through the CLI.

## Non-Goals

- Build a fully automatic semantic migration engine for arbitrary custom role or skill code.
- Rewrite every custom `load.py` file in user projects.
- Hide migration details from the user; the system should surface upgrade guidance explicitly.
- Automatically modify a customized root `.myteam/load.py` during upgrade.

## Strategy

Store the tracked `.myteam` version in a small metadata file at the root of `.myteam/`. The value
represents the `myteam` release that most recently initialized the local agent tree, or that was
later written by a user- or agent-led migration change.

`myteam init` should scaffold three upgrade-supporting elements:

1. The tracked-version metadata file.
2. A root-role `load.py` template that compares the stored version against the installed package
   version and prints an upgrade notice when newer features are available.
3. A built-in `myteam/` skill subtree containing:
   - a parent maintenance skill,
   - a `myteam/migrate` skill that prints pending migration guidance from packaged migration docs,
   - and a `myteam/changelog` skill that prints release notes newer than the tracked version.

Migration itself should be agent-mediated rather than command-driven:

1. The root role warns when the installed `myteam` version is newer than the tracked version.
2. The agent alerts the user of the available migration; if the user approves the migration, continue.
2. The agent loads `myteam/migrate` to read the packaged migration guidance for newer versions.
3. The agent reviews `myteam/changelog` to explain what features were added.
4. The agent proposes concrete edits for the specific project, including any needed changes to
   customized `load.py` files.
5. The user approves those edits before the agent applies them.
6. As part of the approved edits, the tracked `.myteam` version can be updated to the current
   release.

This design keeps migration safe for customized `.myteam` trees. It avoids pretending that a
generic CLI command can correctly rewrite arbitrary project-specific loader logic.

There are three outcomes to alerting the user of the available migration:

- The user approves the migration: the agent implements the changes and updates the stored version
- The user skips the migration: the agent simply updates the stored version
- The user defers the migration: no action taken at this time; the migration will be offered again later.

The migration skill should define these possibilities. 

The migration skill should contain sufficient information that the user could 
explicitly request a multi-version migration if needed (e.g. after skipping multiple versions)
and the agent could find the full migration documentation (not just the default latest version).

## Notes

This feature changes the default `.myteam/` scaffold and the documented upgrade workflow, so it
requires:

1. updates to `src/governing_docs/application_interface.md`,
2. updates to README and packaged changelog text,
3. removal of the `myteam migrate` CLI interface from the command reference and tests.
