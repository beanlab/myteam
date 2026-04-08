# Myteam

`myteam` is a package for building agent systems where agents load their own roles and skills from files on disk.

The core model is simple:

- users define roles, skills, and tools inside `.myteam/`
- agents assume a role by running `myteam get role <role>`
- agents load a skill by running `myteam get skill <skill>`
- each loaded role or skill reveals the next layer of discoverable roles, skills, and tools

This makes `myteam` useful for hierarchical multi-agent systems where instructions should be explicit, inspectable, and
versioned in Git.

## Agent-Centered Workflow

`myteam` is primarily for agents, not humans.

A human author creates the role and skill structure. After that, the intended workflow is that agents load their own
instructions.

Typical flow:

1. A user or top-level agent sets up `.myteam/`.
2. A sub-agent is assigned a role such as `developer`.
3. That sub-agent runs `myteam get role developer`.
4. `myteam` prints the role instructions plus any immediately available child roles, child skills, and tools.
5. If the agent needs a skill, it runs `myteam get skill <skill>`.
6. If the project wants deterministic multi-step orchestration, it can define a named workflow under `.myteam/workflows/` and run `myteam workflows start <name>`.

In other words, roles and skills are loaded by the agent that is assuming them.

## What Happens When An Agent Loads A Role

When an agent runs:

```bash
myteam get role developer
```

`myteam` executes that role's `load.py`, which:

1. Prints the contents of `role.md` or `ROLE.md`
2. Prints built-in guidance about roles, skills, and tools
3. Lists the immediate child roles in that directory
4. Lists the immediate child skills in that directory
5. Lists Python tools in that directory

The same pattern applies to skills:

```bash
myteam get skill python/testing
```

This layered discovery is the main idea behind the package. An agent sees the instructions for its current node and the
next available things it can assume or use.

## Mental Model

`myteam` stores an agent system in plain files.

- A role is a team member with instructions.
- A skill is a reusable capability with instructions.
- A tool is a Python script colocated with a role or skill.
- A roster is a reusable bundle that can be downloaded into `.myteam/`.

Roles and skills are identified by definition files:

- role directories contain `role.md` or `ROLE.md`
- skill directories contain `skill.md` or `SKILL.md`

Each loadable node also has a `load.py` that prints the node's instructions and its immediate discoverable children.

## Quick Start

Initialize a new agent system:

```bash
myteam init
```

This creates:

```text
AGENTS.md
.myteam/
  .myteam-version
  load.py
  role.md
```

The root `.myteam/` directory is the default root role.

The packaged `builtins/` skill tree is available to load, but it is not created inside `.myteam/`.

Edit `.myteam/role.md` with the instructions that should be given to the default agent. Then that agent can load its
instructions with:

```bash
myteam get role
```

The generated root role also tracks the `myteam` version that created the tree. If a newer installed
`myteam` release is available later, the root role can alert the agent to review
`builtins/migration` and `builtins/changelog`.

Create a sub-role and a skill:

```bash
myteam new role developer
myteam new skill python
myteam new skill python/testing
myteam new workflow planning/release
```

That agent system now supports commands like:

```bash
myteam get role
myteam get role developer
myteam get skill python/testing
myteam get workflow planning/release
```

## Directory Structure

Example:

```text
AGENTS.md
.myteam/
  .myteam-version
  load.py
  role.md
  developer/
    load.py
    role.md
  python/
    load.py
    skill.md
    testing/
      load.py
      skill.md
```

In this layout:

- the root agent runs `myteam get role`
- a developer agent runs `myteam get role developer`
- an agent needing the testing skill runs `myteam get skill python/testing`

Discovery is local to the node being loaded. An agent sees only the next layer beneath its current role or skill.

For nested roles or skills to be discoverable, each parent layer must also be defined. For example,
`python/testing` is only visible if `python` itself exists as a loadable node.

## Authoring Roles And Skills

Instruction files are Markdown.

Example `role.md`:

```md
---
name: Developer
description: Implements product changes and fixes
---

You are responsible for writing and validating code changes.
Load relevant skills before implementing complex work.
Delegate frontend work to `frontend` if that role is available.
```

Example `skill.md`:

```md
---
name: Python Testing
description: Test-writing and debugging guidance
---

Prefer focused tests before broad suites.
Use the existing project test helpers where available.
```

Behavior:

- YAML frontmatter is stripped before the instructions are printed to the agent
- `name` and `description` are used for listings when present
- if frontmatter metadata is absent, `myteam` falls back to `info.md` when available

## Commands

### `myteam init`

Creates the root `.myteam/` role and `AGENTS.md` in the current directory.

It also:

- stores the current `myteam` version in `.myteam/.myteam-version`
- makes the packaged `builtins/` maintenance skills available to load later

### `myteam new role <path>`

Creates a new role under `.myteam/` with:

- `role.md`
- `load.py`

Examples:

```bash
myteam new role developer
myteam new role engineer/frontend
```

### `myteam new skill <path>`

Creates a new skill under `.myteam/` with:

- `skill.md`
- `load.py`

The reserved `builtins/` namespace is not available for project-defined skills.

Examples:

```bash
myteam new skill python
myteam new skill python/testing
myteam new skill research
myteam new skill research/literature-review
```

### `myteam get role [path]`

Loads a role's instructions.

- omit `path` to load the root role at `.myteam/`
- use slash-delimited paths for nested roles
- when the root role was scaffolded by `myteam init`, it may print an upgrade notice if the installed
  `myteam` version is newer than the tracked `.myteam` version

Examples:

```bash
myteam get role
myteam get role developer
myteam get role engineer/frontend
```

### `myteam get skill <path>`

Loads a skill's instructions.

Paths under `builtins/` resolve from the packaged built-in skill tree. All other skill paths resolve
from the project's `.myteam/` tree.

Examples:

```bash
myteam get skill python/testing
myteam get skill research/literature-review
```

### `myteam get workflow <name>`

Prints the stored workflow YAML from `.myteam/workflows/<name>.yaml`.

Example:

```bash
myteam get workflow planning/release
```

### `myteam remove <path>`

Deletes a role or skill directory from `.myteam/`.

### `myteam list`

Lists available downloadable rosters from the default roster repository.

### `myteam download <roster>`

Downloads a folder roster into `.myteam/` by default.

By default, the roster path is preserved under `.myteam/`, so `myteam download skills/foo` installs
into `.myteam/skills/foo/`. If you provide a destination path, that path becomes the managed install
root under `.myteam/`.

Each downloaded folder gets a `.source.yml` file at its root so future commands can track where it
came from.

If the destination already exists, `myteam download` fails instead of merging into it:

- if the existing folder is the same managed source, run `myteam update <path>` instead
- if the existing folder is unrelated content, delete it or choose a different destination

### `myteam update [path]`

Refreshes one managed roster install or all managed installs under `.myteam/` from their recorded
source metadata.

This uses the same managed-install behavior as `myteam download` after replacing the existing
managed subtree root.

Single-file roster downloads are not supported.

Useful when you want to seed an agent system from a reusable template instead of authoring it from scratch.

There is no dedicated `myteam migrate` CLI command.

For upgrade work:

- load `myteam get skill builtins/migration` to review packaged migration guidance
- load `myteam get skill builtins/changelog` to review newer release notes
- apply approved project-specific edits manually, including any `.myteam` version-file update

### `myteam new workflow <name>`

Creates `.myteam/workflows/<name>.yaml` from the built-in workflow template.

### `myteam workflows start <name>`

Runs a deterministic workflow YAML from `.myteam/workflows/<name>.yaml` whose top-level step names map to:

- `role`: the `.myteam/` role to load for that step
- `inputs`: structured input values for the step
- `outputs`: the required final JSON keys for the step

Example shape:

```yaml
plan:
  role: .myteam/plan
  inputs:
    request: draft a plan
  outputs:
    summary: short plan summary
    plandoc: /plan.md
review:
  role: review
  inputs:
    summary:
      from: plan.summary
  outputs:
    verdict: review result
```

`myteam workflows start` hides the AppServer mechanics under the hood:

- it launches a local Codex AppServer session
- it creates one fresh thread per step attempt
- it prints a compact step banner with the current step, role, thread id, and available commands
- it streams the active step live
- it keeps the current step thread open so you can send follow-up input on additional turns
- it supports `/help`, `/status`, `/outputs`, and `/done` while a step is active
- it persists run state under `.myteam/workflow_runs/`
- it clearly distinguishes conversation mode from the final structured-output handoff
- it advances after you type `/done` for the current step in interactive use
- after each finalized step, it prints the token usage for that step
- after the workflow completes, it prints the total token usage across all completed steps

For `outputs`:

- a scalar value like `poem: final poem text` means that output is a `string`
- if you need a non-string JSON type, use a mapping such as
  `count: {type: integer, description: line count}`

Only the final validated JSON object from a completed step becomes workflow state for later steps.

### `myteam workflows resume <run_id>`

Resumes the first incomplete step from a failed workflow run while preserving earlier completed
outputs and re-entering the same interactive step UI used by `myteam workflows start`.

### `myteam workflows status <run_id>`

Prints the saved workflow run state without starting the AppServer, including the current step when
present, completed outputs, latest failure, and accumulated workflow token usage.

## Why Use Myteam

- agents load their own instructions directly from the filesystem
- roles and skills are explicit, inspectable, and Git-friendly
- discovery is layered, which fits hierarchical agent systems
- tools can live next to the roles and skills that use them
- rosters let you reuse agent-system structures across projects

## Installation

```bash
pip install myteam
```

## Requirements

- Python 3.11+

## License

MIT
