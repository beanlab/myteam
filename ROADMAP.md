# Workflow Roadmap

This roadmap turns the workflow improvement ideas into a staged plan that stays aligned with
`myteam`'s architecture.

## North Star

Make `myteam workflows` feel like a first-class `myteam` capability:

- workflows live alongside other local `myteam` assets
- users can start them with simple commands
- roles remain the source of behavior
- structured outputs remain the source of deterministic state transfer

## Phase 1: Workflow Ergonomics

Goal: reduce friction for first-time users and make workflows easier to discover.

### Deliverables

- Support workflow lookup under `.myteam/workflows/`
- Allow `myteam workflows start <name>` in addition to path-based execution
- Add `myteam new workflow <name>`
- Scaffold new workflows from a template based on `planning_files/template.yaml`
- Document recommended layout and naming conventions

### Why this phase comes first

The current runner already works, but it still feels file-path-heavy and somewhat internal. This
phase makes workflows feel like a normal `myteam` concept instead of an advanced feature.

## Phase 2: Better Data Flow

Goal: make workflows more reusable and easier to compose without sacrificing determinism.

### Deliverables

- Add top-level workflow `inputs`
- Support `input.<name>` references cleanly in step inputs
- Improve validation and error messages for broken references
- Allow roles to define optional default workflow metadata for input and output contracts
- Keep workflow-level overrides so orchestration remains flexible

### Why this phase matters

Right now many shared values have to be repeated across steps. Root-level inputs and clearer
contracts will make workflows easier to reuse across projects and runs.

## Phase 3: Interactive Workflow UX

Goal: make step-level collaboration clear and reliable for users.

### Deliverables

- Add `/help`, `/status`, `/outputs`, `/retry`, and `/cancel`
- Print a small command banner when each step starts
- Make the terminal clearly distinguish:
  - conversation mode
  - finalization mode
  - completion handoff
- Improve messaging around failed finalization and resume behavior
- Continue showing per-step and total token usage

### Why this phase matters

The biggest usability gain now is not more protocol capability; it is making the current experience
easier to understand while people collaborate with individual workflow threads.

## Phase 4: Richer Status and Recovery

Goal: make workflows easier to inspect, debug, and resume.

### Deliverables

- Expand `myteam workflows status <run_id>` with:
  - current step
  - waiting state
  - finalized outputs
  - per-step token usage
  - total token usage
  - last failure reason
- Improve persistence format so status is more informative without needing to reattach
- Add clearer resume messaging when rerunning the first incomplete step

### Why this phase matters

A deterministic runner becomes much more trustworthy when users can easily see what has happened,
what data was produced, and what will happen on resume.

## Phase 5: Workflow Guidance and Reuse

Goal: help teams write better workflows and reuse roles more effectively.

### Deliverables

- Add a workflow authoring skill to `myteam`
- Document best practices for stable output schemas
- Document role design patterns for workflow reuse
- Provide example workflows for common patterns:
  - linear generation and review
  - plan then implement
  - write then revise
- Explore reusable role-declared output contracts

### Why this phase matters

The workflow feature will be easier to scale across a team if the architecture is taught clearly and
the best patterns are encoded into the tooling ecosystem.

## Suggested Order Of Work

1. Phase 1: Workflow Ergonomics
2. Phase 2: Better Data Flow
3. Phase 3: Interactive Workflow UX
4. Phase 4: Richer Status and Recovery
5. Phase 5: Workflow Guidance and Reuse

## Success Criteria

The roadmap is successful when:

- a new user can create and start a workflow with one or two commands
- workflows feel like a native part of the `myteam` tree
- users can collaborate with a running step without losing deterministic handoff
- the state of a workflow is easy to inspect and resume
- roles stay responsible for behavior while workflows stay responsible for orchestration
