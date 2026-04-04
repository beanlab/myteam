# Deterministic myteam workflows Runner Using Codex Threads

  ## Summary

  Build the first workflow system as a myteam feature, not an
  AppServer feature. The runner should accept a simple YAML shaped
  like [template.yaml](/Users/merleth/Documents/BYU/Winter 2026/CS
  401R/myteam/template.yaml), execute steps strictly in file order,
  and use Codex AppServer threads/turns underneath for each step
  attempt.

  The CLI should be simplified to:

  - myteam workflows start <path_to_workflow_yaml>
  - myteam workflows resume <run_id>
  - myteam workflows status <run_id>

  start is the main entrypoint. It should launch the AppServer
  session, stream the active step live, and allow the user to
  communicate with the currently running step from the same command
  session. All thread creation, turn execution, persistence,
  retries, and protocol handling stay under the hood.

  ## Key Changes

  ### CLI and interaction model

  Use workflows as a top-level command group and make start the
  normal user flow.

  - myteam workflows start <path> loads the workflow, starts the
    run, enters an interactive live session, and streams step events
  - while a step is running, user input typed into the session is
    sent to the active step via turn/steer
  - when a step finishes successfully, the runner automatically
    advances to the next step
  - if a step fails, the run pauses and prints the failure plus the
    saved run_id
  - myteam workflows resume <run_id> reattaches to the saved run and
    continues from the first incomplete step
  - myteam workflows status <run_id> reports current step, completed
    steps, and last failure if any

  Keep the internal persistence model from the earlier draft:

  - .myteam/workflow_runs/<run_id>/run.json
  - per-step attempt records including thread_id, turn_id, final
    message text, validated output object, and failure metadata

  ### YAML format

  Base the v1 format directly on template.yaml:

  step_name:
    role: path/to/role
    inputs:
      key: value-or-reference
    outputs:
      output_name: description-or-schema-hint

  Interpretation rules for v1:

  - the top-level YAML mapping order is the workflow order
  - each top-level key is the step ID
  - role is required
  - inputs is optional and becomes the structured input object for
    the step
  - outputs is required and defines the expected output object shape
    for the step
  - literal scalar values in inputs are passed through as-is
  - string references in inputs may point to:
      - workflow invocation input, via input.<name>
      - previous step outputs, via <step_id>.<output_name>

  Use the last example in template.yaml as the canonical mental
  model:

  - a step named plan
  - a role path
  - named inputs like request
  - named outputs like plandoc and summary

  For determinism, treat outputs as the required output contract,
  not just comments. The implementation should compile that section
  into a JSON schema-like object used for:

  - prompting the step
  - validating the final structured result
  - deciding whether the step completed successfully

  ### Thread, turn, and subprocess model

  Use one fresh Codex thread per step attempt.

  For each step:

  1. Resolve and load the step role instructions using the same
     machinery as myteam get role
  2. Start a fresh AppServer thread with those instructions as the
     step’s base context
  3. Start one turn containing:
      - the step’s resolved structured inputs
      - workflow runner instructions requiring a structured final
        result matching the declared outputs
      - the step-specific task framing
  4. Stream notifications live to the user
  5. While the turn is active, allow user follow-up messages through
     turn/steer
  6. Only mark the step complete when:
      - the turn reaches completed
      - the final assistant message is parseable structured data
      - that data satisfies the declared outputs contract

  This keeps the workflow deterministic while still allowing
  communication with each subprocess:

  - the subprocess stays isolated to one step/thread
  - the user may interact during execution
  - only the validated final structured output is allowed to
    influence later steps

  Do not let freeform intermediate chat become downstream workflow
  state.

  ## Implementation Changes

  ### Framework refactor

  Add reusable internals for:

  - capturing role loader output as instruction text instead of only
    printing it
  - parsing ordered workflow YAML from the template.yaml-style shape
  - resolving input references against workflow invocation input and
    prior validated step outputs
  - validating final step output against the declared outputs
    contract
  - AppServer JSON-RPC session management over stdio, including
    initialize, thread/start, turn/start, turn/steer, and event
    streaming
  ### Feature addition
  Implement myteam workflows around those helpers:

  - start opens an interactive workflow session and hides AppServer
    mechanics
  - resume reloads saved state and restarts at the first incomplete
    step
  - status is read-only and does not touch the AppServer

  The workflow runner should pause cleanly on:

  - invalid final output
  - turn failure
  - interruption
  - transport loss

  On resume, rerun only the first incomplete step in a new thread
  attempt.

  ## Test Plan

  Add tests for:

  - valid template.yaml-style workflows preserving top-level step
    order
  - invalid workflows: missing role, missing outputs, bad
    references, duplicate output names within a step
  - sequential execution where later steps consume only prior
    validated outputs
  - live steering routed to the active step without changing
    previously completed step outputs
  - completed turn with invalid structured output causing the step
    to fail deterministically
  - resume continuing from the first incomplete step only
  - status reflecting persisted run state without launching the
    AppServer

  ## Assumptions And Defaults

  - v1 stays strictly sequential
  - myteam workflows start <path> is the primary user-facing command
  - communication with subprocesses happens through the active
    interactive start or resume session, not through extra public
    subcommands
  - each step gets its own fresh thread for isolation and
    deterministic state boundaries
  - only declared, validated step outputs are promotable to workflow
    state