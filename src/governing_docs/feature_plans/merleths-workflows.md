# Feature Plan: Interactive Workflow TUI

## Pipeline Status

- [x] Create the git branch
- [x] Understand the feature and update the interface document
- [ ] Design the feature
- [ ] Refactor the framework
- [ ] Update the test suite
- [ ] Implement the feature
- [ ] Conclude the feature

## Goal

Improve the terminal experience for `myteam workflows` so users can understand what is happening
while a workflow step runs, what commands are available during a step, and how to inspect the
current run without leaving the active workflow session.

This polish pass should improve the visual feel of the workflow session without changing the
underlying workflow protocol or making the terminal output dependent on color support.

The workflow runner should stay deterministic:

- roles remain the source of step behavior
- workflows remain responsible for orchestration
- step outputs must still be finalized through the existing structured JSON contract
- resuming a failed workflow should preserve already-completed outputs

## Framework Refactor

The current workflow runner mixes display text, input command parsing, and step execution inside
`src/myteam/workflows.py`. The main refactor is to separate "workflow state rendering" from "turn
execution" so richer terminal behavior can be added without scattering `print(...)` statements and
command parsing across the runner.

Planned refactors:

1. Introduce small workflow-TUI helper functions in `src/myteam/workflows.py` for:
   - rendering a step header
   - rendering command help text
   - rendering workflow/run status snapshots
   - rendering finalized/completed output summaries
   - rendering mode transitions such as conversation, finalization, and completion
   - rendering optional terminal styling with plain-text fallback
2. Refactor the step interaction loop so slash-command handling is centralized instead of being
   mixed into the generic follow-up message flow.
3. Add a small status summary helper in the workflow run-state layer or workflow module so both:
   - `myteam workflows status <run_id>`
   - interactive in-step `/status`
   can reuse the same formatting logic.
4. Introduce a tiny styling layer that:
   - applies ANSI styling only for interactive terminals
   - keeps non-interactive output and tests stable
   - separates content styling from workflow logic so future formatting changes stay local
   - can render selected panels with subtle border styling without affecting streamed assistant output
5. Keep the step-execution path unchanged in its core responsibilities:
   - load role instructions
   - start a thread
   - run turns
   - validate final JSON outputs
   - persist attempts and outputs
6. Preserve non-interactive behavior for tests and piped input by keeping the `UserInputPump`
   contract intact and making slash commands work through both tty and non-tty input paths.

The goal of this refactor is to make the runner easier to extend while keeping existing workflow
execution semantics intact.

## Feature Addition

Add a clearer interactive workflow-step terminal experience.

Behavior details:

1. When a step starts, print a compact banner that includes:
   - the step name
   - the step position within the workflow
   - the role used for that step
   - the active thread id
   - the commands available while the step is active
   - clearer visual separation from the streamed assistant output below it
2. The step prompt should clearly indicate conversation mode while the user may still provide
   follow-up guidance to the active thread.
3. The workflow session should use restrained styling, spacing, and alignment so:
   - workflow metadata reads differently from assistant text
   - state transitions such as finalization and completion stand out
   - status and outputs feel like compact panels rather than raw log lines
   - the session remains readable when ANSI styling is unavailable
   - bordered panels are reserved for the workflow chrome that benefits most from them
4. Support the following in-step commands:
   - `/help` to print the available commands again
   - `/status` to print a concise workflow status snapshot for the current run
   - `/outputs` to print completed outputs that are already available from earlier steps
   - `/done` to finalize the current step and request the required JSON object
5. When `/done` is used, print a clear finalization handoff message before the final structured turn
   starts so the user can tell the workflow is no longer in conversation mode.
6. After step completion, print a concise completion summary before moving to the next step.
7. On workflow completion, continue printing total token usage, but make the end-of-run message feel
   like the close of an interactive session rather than just another log line.
8. `myteam workflows status <run_id>` should show richer persisted state, including:
   - current step when present
   - last failure when present
   - completed outputs
   - token totals when available
9. `myteam workflows resume <run_id>` should explain that it is resuming from the first incomplete
   step and then re-enter the same interactive step UI.
10. The active step metadata block and `/help` output should use subtle bordered panels in
    interactive terminals so they read more like TUI surfaces than plain log sections, while
    non-interactive output keeps the existing plain-text layout.

Non-goals for this feature:

- changing the workflow YAML format
- changing how structured output validation works
- adding workflow graph execution or parallel step execution
- changing role loading behavior

## Test Plan

Update the workflow CLI tests to prove:

- workflow start prints the new step banner and command help text
- workflow output remains readable and stable in non-interactive plain-text mode
- `/help` prints the in-step command list without advancing the step
- `/status` prints a useful run snapshot from inside the active workflow session
- `/outputs` prints completed outputs from prior steps while a later step is active
- `/done` transitions the step into finalization and the output still validates correctly
- workflow status reports richer persisted state after completed and failed runs
- workflow resume prints clearer resume messaging and still retries only the first incomplete step
