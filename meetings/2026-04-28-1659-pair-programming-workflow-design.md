# Meeting Notes

Date: April 28, 2026, 4:00pm

# Themes

- workflow output presentation and terminal UX
- Python-based workflow design
- workflow scaffolding and context-loading ergonomics

## Workflow Output Presentation And Terminal UX

Summary:
The discussion focused first on the end-user experience of workflow
runs. The group wants the final output of a completed step to be the
workflow's actual result rather than internal control tokens or raw
session details. They discussed buffering or filtering the terminal
stream so implementation details such as completion markers and
injected prompts do not distract the user, while still preserving
useful session metadata such as which agent or model is being used.

Decisions:
- Treat workflow completion tokens and similar control markers as
  implementation details that should not be shown to users.
- Display step completion with the step's output content instead of
  the raw completion marker.
- Keep the current behavior for now where needed, since correctness
  matters more than cosmetic polish at this stage.

Tasks:
- [Tyler] Change the final step display so completed steps show the
  workflow output rather than the internal completion token.
- [Tyler] Explore formatting the final output in YAML by default,
  with possible JSON support for more machine-chainable output.
- [Tyler] Investigate whether injected prompts and resume text can
  be hidden while still showing useful session-start context.

Open Items:
- Which session metadata should remain visible to users when a new
  step starts?
- Should output formatting default to YAML, JSON, or a user flag?
- How much of the prompt or injected context should be shown in the
  terminal during workflow execution?

## Python-Based Workflow Design

Summary:
The main design discussion centered on moving beyond a YAML-only
workflow format toward Python-based workflows built on a shared
library interface. The idea is to expose an API such as `run_agent`
plus an agent configuration structure so workflows can be written as
ordinary Python scripts. That would allow loops, gates, branching,
and other control flow without inventing a larger workflow language,
while still letting the existing YAML runner map into the same
underlying interface for simple linear workflows.

Decisions:
- Prioritize exploration of Python-based workflows backed by a
  reusable library interface.
- Keep support for simple YAML workflows, but treat them as a thin
  layer over the same underlying agent runner.
- Design the public workflow interface around reusable agent
  definitions, structured outputs, and optional per-agent arguments.

Tasks:
- [Tyler] Design a public Python workflow interface around
  `run_agent` and an agent configuration object.
- [Tyler] Explore how YAML workflow execution can be refactored to
  call the same shared Python interface.
- [Tyler] Investigate support for model selection and other command
  line arguments on a per-step basis.

Open Items:
- Should `myteam start` run Python workflows directly, or should
  users normally run the Python file themselves?
- What is the right shape for the public agent configuration API?
- How should structured outputs be defined and returned to keep the
  interface both ergonomic and machine-friendly?

## Workflow Scaffolding And Context-Loading Ergonomics

Summary:
The conversation also covered tooling around workflow creation and
agent startup. The group wants a `myteam new workflow` command that
generates a Python workflow template with imports and starter code.
They also want workflow-building skills that can help design and
critique workflows, plus the ability to start sessions directly from
roles or skills with context preloaded instead of spending time
loading prompts at runtime.

Decisions:
- Add workflow scaffolding support through a `myteam new workflow`
  command that generates a starter template.
- Explore a workflow-building skill that can help capture design
  requirements and generate workflow code.
- Treat direct role or skill startup with preloaded context as a
  useful near-term feature alongside workflows.

Tasks:
- [Tyler] Add a `myteam new workflow` command that stubs out a
  Python workflow template.
- [Tyler] Explore support for starting a session directly from a
  role or skill with preloaded context.
- [Tyler] Design a skill for building workflows and a later review
  or critique process for workflow quality.
- [Tyler] Continue improving the feature pipeline and related
  workflow support used for release work.

Open Items:
- How should roles and skills be referenced as workflow steps or
  preloaded context?
- What questions should a workflow-building skill ask to collect the
  right step, model, input, and output details?
- When should the system prefer a workflow over simply starting a
  role-focused coding session?
