# Feature Plan: Packaged Built-In Migration Skills

## Pipeline Status

- [x] Create the git branch
- [ ] Plan the feature
- [ ] Update the interface document
- [ ] Refactor the framework
- [ ] Update the test suite
- [ ] Implement the feature
- [ ] Conclude the feature

## Goal

Add a safe upgrade-guidance flow for existing `.myteam/` trees so projects created by older
`myteam` releases can discover packaged migration skills, inspect the relevant instructions, and let
an agent propose project-specific edits instead of relying on copied built-in skill files inside the
project tree.

## Desired Outcome

- [x] Keep using the current `migration-command` branch for this work.
- [x] Define a persistent version marker inside `.myteam/`.
- [x] Ensure `myteam init` writes the current `myteam` version into a newly created `.myteam/`.
- [ ] Stop copying built-in maintenance skills into `.myteam/` during `myteam init`.
- [ ] Keep built-in maintenance skills inside the installed Python package, under the reserved
  `myteam/` prefix.
- [ ] Add a utility surface for packaged built-in skills so they can be listed alongside project
  skills during discovery.
- [ ] Resolve `myteam get skill <path>` by checking project-local `.myteam/` skills first, then
  packaged built-in skills, then failing clearly if neither exists.
- [ ] Update the default root role loader so it warns when the installed `myteam` version is newer
  than the stored `.myteam` version and tells the agent how to proceed if the user approves a
  migration.
- [ ] Provide a packaged `myteam/migration` skill that exposes migration guidance derived from the
  packaged migration documents.
- [ ] Provide a packaged `myteam/changelog` skill that exposes changelog entries newer than the
  stored `.myteam` version.
- [x] Remove the `myteam migrate` CLI command and any command-oriented migration behavior.
- [ ] Add high-level tests that exercise packaged built-in skill discovery, loading, and the
  version-mismatch prompt flow through the CLI.

## Non-Goals

- Build a fully automatic semantic migration engine for arbitrary custom role or skill code.
- Rewrite every custom `load.py` file in user projects.
- Hide migration details from the user; the system should surface upgrade guidance explicitly.
- Automatically modify a customized root `.myteam/load.py` during upgrade.
- Copy or sync packaged built-in maintenance skills into each project's `.myteam/` tree.

## Strategy

Store the tracked `.myteam` version in a small metadata file at the root of `.myteam/`. The value
represents the `myteam` release that most recently initialized the local agent tree, or that was
later written by a user- or agent-led migration change.

`myteam init` should scaffold only the project-owned upgrade-supporting elements:

1. The tracked-version metadata file.
2. A root-role `load.py` template that compares the stored version against the installed package
   version and prints an upgrade notice when newer features are available.

Packaged maintenance skills should live inside `src/myteam/` similarly to templates and migrations.
They are not copied into `.myteam/`. The reserved built-in namespace is `myteam/`.

Skill discovery and loading should work as follows:

1. Project-local skills under `.myteam/` remain the primary source of truth.
2. Packaged built-in skills are exposed as a secondary source under the `myteam/` prefix.
3. `myteam get skill <path>` first resolves the requested skill from `.myteam/`.
4. If no project-local skill exists, `myteam get skill <path>` checks the packaged built-ins.
5. If neither source contains the skill, the command fails with the current clear error path.

This preserves local override behavior while making packaged maintenance skills always available to
legacy projects that never received copied built-ins.

Migration itself should be agent-mediated rather than command-driven:

1. The root role warns when the installed `myteam` version is newer than the tracked version.
2. The warning text should explicitly say the agent can assist with migrating the existing
   `.myteam/` tree.
3. The warning text should also say that if the user agrees, the agent should load
   `myteam get skill myteam/migration` in order to perform the migration correctly.
4. The agent alerts the user of the available migration and waits for approval before taking
   migration steps.
5. After approval, the agent loads `myteam/migration` to read the packaged migration guidance for
   newer versions.
6. The agent may also review `myteam/changelog` to explain what features were added.
7. The agent proposes concrete edits for the specific project, including any needed changes to
   customized `load.py` files.
8. The user approves those edits before the agent applies them.
9. As part of the approved edits, the tracked `.myteam` version can be updated to the current
   release.

This design keeps migration safe for customized `.myteam` trees. It avoids pretending that a
generic CLI command can correctly rewrite arbitrary project-specific loader logic, while also
avoiding the brittle bootstrap problem caused by copying built-in skills into project directories.

There are three outcomes to alerting the user of the available migration:

- The user approves the migration: the agent implements the changes and updates the stored version.
- The user declines the migration: no migration edits are made and the stored version is not updated.
- The user defers the migration: no action is taken at this time; the migration will be offered
  again later.

The migration skill should define these possibilities. 

The migration skill should contain sufficient information that the user could 
explicitly request a multi-version migration if needed (e.g. after skipping multiple versions)
and the agent could find the full migration documentation (not just the default latest version).

## Design Notes

- The built-in skill name should be `myteam/migration`, not `myteam/migrate`, to match the
  user-facing wording in the root-role prompt.
- Packaged built-in skills need a loading path that does not assume their `load.py` lives inside
  the project `.myteam/` tree. The current built-in load templates depend on `__file__` being under
  `.myteam/`, so the implementation should introduce an explicit way for packaged skills to find the
  active project root and print their definition content.
- Discovery output should make packaged built-ins appear like regular skills from the agent's point
  of view, even though they are sourced from the installed package rather than the project tree.

## Notes

This feature changes the default upgrade workflow and the documented skill-loading model, so it
requires:

1. updates to `src/governing_docs/application_interface.md`,
2. updates to README and packaged changelog text,
3. updates to command reference and tests to describe packaged built-in skill resolution,
4. removal of any remaining documentation that says `init` scaffolds built-in maintenance skills
   into `.myteam/`.
