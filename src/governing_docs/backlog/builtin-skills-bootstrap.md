# Built-In Skills Bootstrap Design

## Summary

The current upgrade-guidance design assumes a project can load built-in maintenance skills such as
`myteam/migrate` and `myteam/changelog`. That assumption fails for legacy `.myteam/` trees created
before those built-in skills existed.

We need a simple bootstrap path that installs or refreshes the latest built-in skills without
pretending to perform a full project migration.

## Problem

For a newly initialized project, `myteam init` scaffolds:

- `.myteam/.myteam-version`
- the default root `load.py`
- built-in maintenance skills under `.myteam/myteam/`

For an older project, those files may be missing. In that case:

- the legacy root role cannot necessarily surface the new skill-based migration flow
- `myteam get skill myteam/migrate` cannot work because the skill does not exist yet
- the user has no clean way to "get the latest built-in skills" without hand-copying files

That means the current design does not provide a usable bootstrap path for the very projects that
most need migration guidance.

## Goals

- Provide a simple, explicit way to install the latest built-in skills into an existing project.
- Keep project-specific migration changes agent-mediated rather than automatic.
- Avoid overwriting custom project roles or skills unrelated to the built-in maintenance subtree.
- Make the legacy-project path discoverable from normal `myteam` usage.

## Proposed Direction

Add a narrow command whose job is only to install or refresh the built-in `myteam` maintenance
subtree and other default support files that are safe to add without touching project-specific
content.

For design discussion, the exact command name is open. The important behavior is:

- install missing built-in maintenance skills under `.myteam/myteam/`
- optionally add a missing `.myteam/.myteam-version` file
- optionally refresh the default root loader when the project is still using the uncustomized
  scaffolded loader
- do not rewrite arbitrary custom roles, skills, or loaders
- do not claim to complete migration automatically

After this bootstrap command runs, the user or agent should be able to load:

- `myteam get skill myteam/migrate`
- `myteam get skill myteam/changelog`

## `init` As Bootstrap

We should explicitly consider whether `myteam init` itself should handle this case.

Possible `init` behavior:

- if `.myteam/` does not exist, create the full default scaffold as it does now
- if `.myteam/` already exists, create any missing built-in maintenance files and metadata files
  that are known-safe to add
- leave unrelated existing project files untouched
- fail only when the existing tree is in a state that makes even safe bootstrap ambiguous

This would make `myteam init` double as both:

- first-time initialization
- "install missing built-in defaults" for older trees

Questions to resolve:

- Is it acceptable for `init` to become non-destructive and partially additive when `.myteam/`
  already exists?
- Would users find that behavior intuitive, or would a dedicated bootstrap command be clearer?
- If `init` becomes additive, what exact files are safe to create or refresh automatically?
- Should `init` ever update `.myteam/.myteam-version`, or should that remain a deliberate step
  taken only after project-specific migration work is approved?

## User Alerting

The executable should help users discover the bootstrap path.

One option:

- when `myteam` loads a root role and sees that the installed package version is newer than the
  stored `.myteam` version, print a notice telling the user to run `myteam init` to install any new
  built-in skills

We should also handle the case where the stored version file is missing entirely. A legacy tree with
no tracked version should still receive a useful notice that points toward the bootstrap step.

If `init` is not chosen as the bootstrap mechanism, the same alerting idea should point to the new
dedicated command instead.

## Scope Boundaries

- This work should not perform a full semantic migration of arbitrary project logic.
- This work should not overwrite custom role or skill instructions outside the built-in subtree.
- This work should not silently mark a project as fully migrated when only the built-in skills were
  installed.

## Open Questions

- Should the bootstrap command refresh built-in files every time, or only create missing ones?
- Should bootstrap update the root loader only when it exactly matches an older built-in template?
- Should bootstrap be a new command, or should `init` absorb this behavior?
- What wording best communicates that "built-in skills are now available" is different from "your
  project migration is complete"?
