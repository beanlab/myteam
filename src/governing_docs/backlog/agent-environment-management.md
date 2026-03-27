# Agent Environment Management Design

## Summary

`myteam` needs a first-class way to describe and prepare execution environments for agent tools
without weakening sandbox approval semantics.

The central constraint is that agent harness permissions are prefix-based. A generic approved prefix
such as:

- `source .env`
- `set -a; source .env; ...`
- `.venv/bin/python`
- `myteam run ...`

can become too broad if it effectively means "enter an environment and then do anything."

So the design should not be "teach agents to activate an environment first." The design should be:

- declare environments explicitly
- bind tools to specific environments
- resolve each tool to a concrete executable invocation
- keep approval prefixes specific to the actual tool, not to a generic environment bootstrap step

## Problem

Current guidance is informal:

- if a local `.venv` exists, try `venv/bin/python -m myteam ...`
- if a tool-owning role or skill has a `venv`, use that `venv`

This is not enough as the system grows.

Problems:

- there is no explicit environment model in the project tree
- agents have to guess whether to use system Python, a local `venv`, or something else
- environment variables are often loaded through shell setup commands that make approval prefixes
  overly powerful
- a single approved prefix can accidentally authorize a large class of unrelated actions
- third-party skills and tools will make environment guessing even less reliable

## Goals

- Give `myteam` a clear, inspectable environment model for agent-executed tools.
- Preserve the intent of prefix-based sandbox approvals.
- Make the environment needed for a tool discoverable from the same local tree as the tool itself.
- Reduce ad hoc shell activation and `source`-based workflows.
- Support both Python virtual environments and environment-variable loading as common cases.
- Keep runtime execution local-only and deterministic.

## Non-Goals

- Full package-manager orchestration for every ecosystem.
- Replacing the external harness approval model.
- Automatically trusting arbitrary environment-loading scripts.
- Making all commands run through one generic catch-all launcher.

## Core Design Principle

Environment setup should be treated as configuration attached to a specific tool invocation, not as
a standalone shell session the agent enters.

That means the object that should become approvable is not:

- "activate this environment"

It is:

- "run this specific tool, with this declared executable and these declared environment sources"

## Proposed Model

### 1. Named runtimes

Add a declarative runtime concept. A runtime is a named execution environment that can be referenced
by tools.

Examples:

- `python/default`
- `python/notebook`
- `canvas/api`
- `node/docs`

A runtime declaration should include only the information needed to build a concrete process
invocation, for example:

- runtime kind, such as `python-venv`
- path to interpreter or executable root
- optional environment variable sources
- optional fixed environment variables
- optional working directory rules

### 2. Tool declarations reference runtimes

Today tools are just discovered as `.py` files colocated with roles and skills. That is convenient,
but it is not enough to express execution requirements safely.

We likely need a small manifest layer for tools, for example adjacent metadata that says:

- this tool's entry point is `list_active_courses.py`
- run it with runtime `canvas/api`
- expose it to agents as `list_active_courses`

The important shift is that the tool definition owns the environment binding.

### 3. Resolve to concrete command vectors

`myteam` should be able to resolve a tool plus runtime to an exact argv, not to a shell snippet.

Good:

- `["/abs/project/.venv/bin/python", "canvas/list_active_courses.py"]`
- `["/abs/project/.venv/bin/pytest", "tests/test_cli.py"]`

Risky:

- `["bash", "-lc", "source .env; source .venv/bin/activate; pytest ..."]`

If an environment variable file must be loaded, `myteam` should model that as explicit process
environment construction, not as a generic shell prelude whenever possible.

### 4. Generated per-tool launchers, not one generic runner

If the agent harness needs stable prefixes for approval, `myteam` should prefer generating narrow,
per-tool launcher scripts or commands rather than one generic runner.

For example:

- `.myteam/.bin/list-active-courses`
- `.myteam/.bin/render-dashboard`
- `.myteam/.bin/pytest-project`

Each launcher would have a single declared target tool and runtime. Its behavior would be limited to
that binding.

This is much safer than approving a broad prefix like:

- `myteam run`
- `bash -lc set -a; source .env; ...`

because the prefix itself still names the specific capability being granted.

## Why Per-Tool Launchers

The harness approval model is about intent. A launcher should preserve that intent at the prefix
level.

A specific launcher path communicates:

- what tool is being run
- which environment contract applies
- that the approval is scoped to one declared capability

A generic runtime-entry command hides too much.

For example, approving:

- `.myteam/.bin/list-active-courses`

is meaningfully narrower than approving:

- `myteam env exec canvas/api`

even if both eventually execute the same Python interpreter.

## Environment Variables

Environment variables need a stricter model than "source whatever file exists."

Recommended direction:

- allow declarative env files, such as `.env`
- allow explicit key allowlists or fixed variables
- load them in `myteam` code or a generated launcher, not through arbitrary shell sourcing, when the
  format is structured enough to parse safely

Near-term supported sources could be intentionally limited:

- `.env`-style key/value files
- fixed inline variables in manifest metadata

Avoid, at least initially:

- arbitrary shell scripts as env sources
- commands whose purpose is "prepare a shell for later commands"

If users need arbitrary shell sourcing, that should be treated as an escape hatch with a visibly
higher trust bar.

## Runtime Kinds

Near-term runtime kinds could be small and explicit.

### `python-venv`

Fields:

- `venv_path`
- optional default module runner or executable names
- optional env file references

Resolution:

- use `venv_path/bin/python`
- or use specific executables from `venv_path/bin/...`

### `python-interpreter`

Fields:

- `python_path`
- optional env file references

### `command-prefix`

This should exist only as a constrained compatibility escape hatch for cases that cannot yet be
modeled directly. It is risky because it can collapse back into broad approval semantics.

If included at all, it should:

- be clearly marked as high-trust
- not be the recommended default
- ideally be excluded from auto-generated approvable launchers

## Project Structure Options

There are two plausible homes for runtime metadata.

### Option A: node-local manifests

Each role or skill can declare runtimes for the tools it owns.

Pros:

- local and composable
- keeps ownership near the tool
- fits the existing colocated-tree model

Cons:

- duplicated runtime definitions across neighboring nodes
- harder to share one environment across many tools

### Option B: project-level runtime registry

Add a central runtime registry under `.myteam/`, then let tools reference entries by name.

Pros:

- easier sharing and auditing
- one place to inspect environment policy
- simpler for per-project standard runtimes

Cons:

- weakens locality
- can become a dumping ground if not scoped carefully

Recommended direction:

- use a project-level runtime registry
- let node-local tool manifests reference it

This is the clearest model for reuse and auditing.

## CLI Surface Ideas

The CLI should separate three concerns:

1. describing runtimes
2. materializing launchers
3. running diagnostics

Possible commands:

- `myteam env list`
- `myteam env doctor [runtime]`
- `myteam tool list`
- `myteam tool doctor <tool>`
- `myteam tool install-launchers`

Potentially also:

- `myteam tool resolve <tool>`

which would print the exact argv and environment inputs for debugging.

### Avoid a broad `myteam run`

A generic `myteam run <tool>` is tempting, but it creates the wrong approval target. Even if it is
useful for humans, it should not be the primary story for agent harness integration.

If such a command exists, it should be positioned as a debugging convenience, not the core
approvable interface.

## Suggested File Model

One possible layout:

```text
.myteam/
  runtimes.yml
  tools/
    list-active-courses.yml
    pytest-project.yml
  .bin/
    list-active-courses
    pytest-project
```

Where:

- `runtimes.yml` declares named runtimes
- `tools/*.yml` declares tools and their runtime binding
- `.bin/` is generated output, not hand-edited source

This keeps declarations inspectable and launchers disposable.

## Execution Semantics

When `myteam` materializes a launcher, the launcher should:

1. load only the declared env sources
2. set only the declared fixed variables
3. exec the declared interpreter or executable
4. invoke only the declared tool entry point

It should not:

- open a generic interactive shell
- source arbitrary shell code unless explicitly configured through a high-trust escape hatch
- provide a reusable environment session for later commands

## Relationship To Existing `myteam` Concepts

This environment model fits naturally with existing roles, skills, and tools:

- roles and skills still provide discovery and instructions
- tools remain the executable units
- runtimes become explicit support objects that tools depend on

That is better than overloading role `load.py` or skill `load.py` to perform runtime activation.

## Security Notes

This feature must be designed around least surprise:

- an agent should be able to inspect what a launcher will do
- a user should be able to approve one tool without implicitly approving many others
- environment loading should be declarative where possible

The biggest risk is accidentally reintroducing a generic shell bootstrap under a more structured
name. The design should resist that.

## Implementation Strategy

### Phase 1: metadata and resolver

- define runtime and tool manifests
- implement parsing and validation
- implement command resolution to exact argv plus environment

### Phase 2: launcher generation

- generate per-tool launchers under a managed directory such as `.myteam/.bin/`
- keep launchers deterministic and inspectable
- add diagnostics for missing interpreters, missing venvs, and malformed env files

### Phase 3: documentation and integration

- update tool guidance so agents prefer declared launchers over ad hoc activation
- update templates and built-in instructions
- decide how launcher paths should be surfaced in role and skill discovery output

## Open Questions

- What manifest format is the right balance between readability and strictness?
- Should tool declarations remain optional, or eventually become the preferred way to expose tools?
- Should `myteam` generate POSIX shell launchers, Python launchers, or both?
- How should Windows support be handled if launcher generation becomes part of the public contract?
- Should `.env` loading support interpolation, or only literal key/value parsing?
- Is there any acceptable form of shell-based env activation that still preserves approval intent?
