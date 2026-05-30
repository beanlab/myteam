# Myteam

`myteam` is a package for building agent systems where agents load their own roles and skills from files on disk.

The core model is simple:

- users define roles and skills inside `.myteam/`
- agents assume a role by running `myteam get role <role>`
- agents load a skill by running `myteam get skill <skill>`
- each loaded role or skill reveals the next layer of discoverable roles and skills

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
4. `myteam` prints the role instructions plus any immediately available child roles, child skills, and tasks.
5. If the agent needs a skill, it runs `myteam get skill <skill>`.

In other words, roles and skills are loaded by the agent that is assuming them.

## What Happens When An Agent Loads A Role

When an agent runs:

```bash
myteam get role developer
```

`myteam` executes that role's `load.py`, which:

1. Prints the contents of `role.md` or `ROLE.md`
2. Prints built-in guidance about roles and skills
3. Prints built-in guidance about runnable tasks
4. Lists the immediate child roles in that directory
5. Lists the immediate child skills in that directory
6. Lists the immediate child tasks in that directory

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

If you want a different project-local root, pass `--prefix <path>` to the supported commands. For
example, `myteam init --prefix .agents` creates the root role under `.agents/`.

The packaged `builtins/` skill tree is available to load, but it is not created inside `.myteam/`.

Edit `.myteam/role.md` with the instructions that should be given to the default agent. Then that agent can load its
instructions with:

```bash
myteam get role
```

The generated root role also tracks the `myteam` version that created the tree. If a newer installed
`myteam` release is available later, the root role can alert the agent to review
`builtins/migration` and `builtins/changelog`.

The packaged changelog ships inside the installed `myteam` package and can be printed directly with:

```bash
myteam changelog
```

Create a sub-role and a skill:

```bash
myteam new role developer
myteam new skill python
myteam new skill python/testing
```

That agent system now supports commands like:

```bash
myteam get role
myteam get role developer
myteam get skill python/testing
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

### `myteam init [--prefix <path>]`

Creates the root role in the selected local root and `AGENTS.md` in the current directory.

It also:

- stores the current `myteam` version in the local root's `.myteam-version`
- makes the packaged `builtins/` maintenance skills available to load later

Use `--prefix <path>` to scaffold the local tree somewhere other than `.myteam/`.

### `myteam new role <path> [--prefix <path>]`

Creates a new role under the selected local root with:

- `role.md`
- `load.py`

Examples:

```bash
myteam new role developer
myteam new role engineer/frontend
myteam new role developer --prefix .agents
```

### `myteam new skill <path> [--prefix <path>]`

Creates a new skill under the selected local root with:

- `skill.md`
- `load.py`

The reserved `builtins/` namespace is not available for project-defined skills.

Examples:

```bash
myteam new skill python
myteam new skill python/testing
myteam new skill research
myteam new skill research/literature-review
myteam new skill python/testing --prefix .agents
```

### `myteam new workflow [path] [--prefix <path>]`

Creates a new Python workflow file under the selected local root.

- omit `path` to create the default `agent.py` at the selected local root
- use slash-delimited paths for nested workflows such as `automation/daily`
- the scaffolded file contents match the repository's default `.myteam/agent.py`

Examples:

```bash
myteam new workflow
myteam new workflow automation/daily
myteam new workflow --prefix .agents
```

### `myteam get role [path] [--prefix <path>]`

Loads a role's instructions.

- omit `path` to load the root role at the selected local root
- use slash-delimited paths for nested roles
- when the root role was scaffolded by `myteam init`, it may print an upgrade notice if the installed
  `myteam` version is newer than the tracked version for that local root

Examples:

```bash
myteam get role
myteam get role developer
myteam get role engineer/frontend
myteam get role developer --prefix .agents
```

### `myteam get skill <path> [--prefix <path>]`

Loads a skill's instructions.

Paths under `builtins/` resolve from the packaged built-in skill tree. All other skill paths resolve
from the selected project-local tree.

Examples:

```bash
myteam get skill python/testing
myteam get skill research/literature-review
myteam get skill python/testing --prefix .agents
```

### `myteam get_skills [directory] [--prefix <path>]`

Prints detailed skill metadata for the child skills available in a directory. Omit `directory` to
use the selected local root.

Examples:

```bash
myteam get_skills
myteam get_skills developer
myteam get_skills developer --prefix .agents
```

### `myteam get_tasks [directory] [--prefix <path>]`

Prints detailed task metadata for the supported workflow files available in a directory. Each task
entry prints its `name`, `description`, and `input` frontmatter when present. Supported workflow
files use `.py`, `.md`, `.yaml`, and `.yml` suffixes. Omit `directory` to use the selected local
root.

Examples:

```bash
myteam get_tasks
myteam get_tasks research
myteam get_tasks research --prefix .agents
```

### `myteam get task <path> [--prefix <path>]`

Prints the detailed contents for a single task file, including frontmatter metadata when present
and the task prompt body for markdown tasks.

Examples:

```bash
myteam get task research/summary
myteam get task research/summary.md
myteam get task research/summary --prefix .agents
```

### `myteam start [path] [--prefix <path>] [--verbose]`

Executes a workflow definition from the selected local root.

- use slash-delimited workflow paths such as `dev/frontend`
- workflow paths are resolved starting from the selected local root, which acts as the reference point for lookup
- relative segments in workflow paths are allowed
- workflow files are resolved with standard YAML extensions or `.py`
- later workflow steps may reference completed state from earlier steps
- Python workflow files may resume or fork related agent sessions by passing a prior
  `StepResult.session_id` into `run_agent(...)` as `session_id`, with `fork=True` to fork
- Python workflow files may pass `cwd` to `run_agent(...)` to override the default agent launch
  directory
- role and skill directories are not valid `start` targets
- omitting the path runs the default `agent` workflow

Examples:

```bash
myteam start dev/frontend
myteam start release/checklist --prefix .agents
myteam start dev/frontend --verbose
```

### `myteam task result [--json <json> | --text <text>]`

Submits the structured result for the current task step.

This command is primarily agent-facing. Task prompts use it to report a final payload back to
the parent task runner over the private result channel for that step.

Examples:

```bash
myteam task result --json '{"summary":"done"}'
myteam task result --text "done"
printf '{"summary":"done"}\n' | myteam task result
```

### `myteam task start <task> --session-nonce <nonce> [--json <json> | --text <text>]`

Requests that the current task step start a child task by name.

This command is primarily agent-facing. Task prompts use it to ask the parent runner to launch
another task over the private control channel for that step.

Examples:

```bash
myteam task start follow-up --session-nonce abc123 --json '{"task":"review"}'
myteam task start follow-up --session-nonce abc123 --text "review"
printf '{"task":"review"}\n' | myteam task start follow-up --session-nonce abc123
```

### `myteam changelog`

Prints the packaged `myteam` changelog from the installed release.

This command reads the same packaged changelog source used by `builtins/changelog`.

### `myteam remove <path> [--prefix <path>]`

Deletes a role or skill directory from the selected local root.

Use `--prefix <path>` to remove from a different local root.

### `myteam list`

Lists available downloadable rosters from the default roster repository.

### `myteam download <roster> [destination] [--prefix <path>]`

Downloads a folder roster into the selected local root by default.

By default, the roster path is preserved under `.myteam/`, so `myteam download skills/foo` installs
into `.myteam/skills/foo/`. If you provide a destination path, that path becomes the managed install
root under `.myteam/`.

Use `--prefix <path>` to change that default managed root. For example,
`myteam download skills/foo --prefix .agents` installs into `.agents/skills/foo/`.

Each downloaded folder gets a `.source.yml` file at its root so future commands can track where it
came from.

If the destination already exists, `myteam download` fails instead of merging into it:

- if the existing folder is the same managed source, run `myteam update <path>` instead
- if the existing folder is unrelated content, delete it or choose a different destination

### `myteam update [path] [--prefix <path>]`

Refreshes one managed roster install or all managed installs under the selected local root from their
recorded source metadata.

Use `--prefix <path>` to scan or resolve managed installs under a different local root.

This uses the same managed-install behavior as `myteam download` after replacing the existing
managed subtree root.

Single-file roster downloads are not supported.

Useful when you want to seed an agent system from a reusable template instead of authoring it from scratch.

There is no dedicated `myteam migrate` CLI command.

For upgrade work:

- load `myteam get skill builtins/migration` to review packaged migration guidance
- load `myteam get skill builtins/changelog` to review newer release notes
- apply approved project-specific edits manually, including any `.myteam` version-file update

## Workflows

*Note: workflows are an experimental feature and are likely to evolve and change*

`myteam` can also run authored workflows from the project-local tree.

Store workflow files under the selected local root. For example, this command:

```bash
myteam start dev/frontend
```

looks for a workflow file such as:

```text
.myteam/dev/frontend.yaml
```

If you use `--prefix .agents`, the same workflow path is resolved under `.agents/` instead.
The selected local root is the reference point for resolution, not a containment boundary.

YAML workflow files are mappings where each top-level key is a step name. Each step defines:

- `prompt`: the objective for that step
- `agent`: optional agent name; omit it to use the default agent
- `input`: optional structured input data
- `output`: the expected shape of the step's final structured result

Example:

```yaml
gather_context:
  prompt: Review the current implementation and summarize the relevant files.
  output:
    summary: Brief summary
    files:
      primary: Main file path
      tests: Test file path

draft_change:
  prompt: Propose the implementation plan for the requested change.
  input:
    prior_summary: $gather_context.output.summary
    primary_file: $gather_context.output.files.primary
  output:
    plan: Concise implementation plan
    risks: Key risks or open questions
```

Notes:

- step names should use identifier-style names such as `gather_context`
- `$step_name.output...` references pull data from earlier completed steps
- the step agent reports its final structured result by calling `myteam task result`
- the step agent can request a nested task by calling `myteam task start`
- `myteam start` stops at the first failing step and does not continue to later steps
- `--verbose` writes workflow lifecycle logs to standard error
- successful `myteam start` runs currently mirror workflow session terminal output; they do not yet
  print a separate final structured payload on stdout

Python workflow files ending in `.py` are run as scripts in a separate Python process. The child
process uses the directory containing the workflow file as its current working directory, receives
the selected local root in `MYTEAM_PROJECT_ROOT`, and returns its exit status directly through
`myteam start`.

## Why Use Myteam

- agents load their own instructions directly from the filesystem
- roles and skills are explicit, inspectable, and Git-friendly
- discovery is layered, which fits hierarchical agent systems
- rosters let you reuse agent-system structures across projects
- workflows let you create predefined, deterministic agent workflows

## Installation

```bash
pip install myteam
```

## Requirements

- Python 3.11+

## License

MIT
