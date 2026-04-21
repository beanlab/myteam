# Python Workflow Authoring And API

## Summary

`myteam` workflows are currently authored in YAML and executed through the CLI. That is useful for
simple declarative orchestration, but it is limiting for developers who want to compose agent steps
inside their own Python code, reuse normal language abstractions, or scaffold richer workflow logic
without dropping down into internal runtime modules.

We want a convenient developer-facing code interface for running agent steps directly from Python,
plus first-class support for authoring workflows in Python instead of only YAML.

## Problem

The current workflow experience is skewed toward authored YAML files and CLI execution.

That leaves several gaps:

- developers do not have a clean public Python API for "run one agent step"
- workflow authors cannot use normal Python control flow, helper functions, or composition patterns
- there is no `myteam new workflow` scaffolding flow comparable to `new role` or `new skill`
- agents do not yet have guidance for building Python-based workflows if that becomes a supported
  authoring path

This creates friction for both humans and agents:

- developers may reach into internal modules instead of using a stable interface
- more complex workflow logic becomes awkward or impossible to express cleanly in YAML
- the product lacks a clear "starting point" for Python workflow authoring

## Goals

- Provide a stable Python API for running agent steps from developer code.
- Support workflow authoring in Python as a first-class option alongside YAML.
- Add scaffolding so `myteam new workflow` creates an obvious starting structure.
- Keep the developer-facing interface simple enough for common one-agent or few-step use cases.
- Consider agent guidance so Python workflow support is discoverable and usable by agents too.

## Proposed Change

Introduce a public Python workflow authoring surface with three related pieces.

### 1. Public Python step-execution API

Expose a supported code interface that lets developers run an agent step from Python without
importing internal implementation details directly.

The initial use case should be simple and ergonomic:

- create or configure a workflow/session runner
- run a generic agent step with prompt/input/output expectations
- receive structured result data

This API should be designed intentionally as public surface area rather than as a thin leak of
current internal modules.

### 2. Python-authored workflows

Allow developers to define workflows in Python instead of only YAML.

That could mean:

- a Python entrypoint that assembles and runs steps imperatively
- a small Python DSL over the workflow engine
- or a builder-style interface that mirrors the YAML concepts while allowing code composition

The authoring model should make it easy to start simple and grow into richer logic when needed.

### 3. `myteam new workflow` scaffolding

Add a workflow scaffolding command that creates a starter Python workflow structure, likely a
`workflow.py` file or workflow folder with a small PyFire-based entrypoint.

The first generated template should be minimal and practical:

- runnable from the CLI
- stubbed to execute a single generic agent session
- easy to extend into multiple steps later

The scaffolding should establish the recommended conventions for Python workflows, not just create an
empty file.

### 4. Optional workflow-building skill

If Python workflows become a supported authoring mode, add a skill that teaches agents how to create
and extend them correctly.

That skill could cover:

- when to choose Python workflows over YAML
- the expected public API usage
- recommended structure for simple versus multi-step workflows
- how to keep Python workflows readable and stable

## Scope Boundaries

- This item is about public developer authoring interfaces, not only internal workflow refactors.
- This does not require removing YAML workflow support.
- This does not require supporting every advanced orchestration feature in the first Python API.
- The optional skill should follow the product design rather than driving it prematurely.

## Open Questions

- Should Python workflows be loadable through `myteam start`, a separate command, or both?
- What is the smallest clean public API for "run one agent step" without overcommitting to current
  internals?
- Should `myteam new workflow` default to a single `workflow.py` file, or a folder with template
  helpers and tests?
- How closely should Python workflow concepts mirror YAML workflow fields?
- Should the skill ship with the first Python workflow release, or follow after the interface
  stabilizes?
