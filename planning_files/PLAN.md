# Deterministic myteam Workflow Runner on Top of Codex Threads

  ## Summary

  Add a myteam-side workflow runner that treats Codex AppServer as
  an execution engine, not as something to redesign. The runner will
  load a local YAML workflow, execute steps strictly in order,
  create one fresh Codex thread per step attempt, and only advance
  when the step’s final assistant message is valid structured
  output.

  This follows the meeting decisions directly:

  - minimal new infrastructure: reuse existing initialize, thread/
    start, turn/start, and streamed notifications
  - structured outputs: every step publishes a typed object, never
    “best effort” prose
  - staged information quality: the example workflow should encode
    the agreed sequence of interface clarification, framework
    refactor, implementation design, test updates, implementation,
    and review

  ## Key Changes

  ### Public CLI and runtime behavior

  Add a new top-level CLI group:

  - myteam workflow run <workflow_path> --input-file <json> [--app-
    server-command "..."]
  - myteam workflow resume <run_id> [--app-server-command "..."]
  - myteam workflow status <run_id>

  Defaults:

  - workflow_path is a normal filesystem path relative to the
    project root
  - recommended project convention is .myteam/workflows/*.yml
  - default AppServer launch command is codex app-server; allow
    override via CLI flag and matching env var
  - each run or resume launches a local AppServer subprocess over
    stdio, sends initialize, then executes steps

  Persist run state locally under .myteam/workflow_runs/<run_id>/:

  - run.json with workflow metadata, status, resolved input, and
    step index
  - one step-attempt record per attempt containing thread_id,
    turn_id, timestamps, raw final message text, parsed output
    object, and error details

  ### Workflow definition format

  Use YAML with this v1 shape:

  - top-level fields: version, name, optional description, optional
    defaults, optional input_schema, required steps
  - defaults may include: cwd, model, model_provider,
    approval_policy, sandbox, service_name
  - each step requires: id, role, prompt, output_schema
  - each step may include: step-local overrides matching the same
    defaults, plus inputs

  Use strict sequential execution only:

  - steps is an ordered list
  - no branching, no DAG scheduling, no conditional transitions in
    v1

  Use deterministic reference syntax for step inputs:

  - workflow input reference: input#/json/pointer
  - prior step output reference: steps.<step_id>#/json/pointer

  Resolved step inputs are materialized into one JSON object before
  execution and become the only machine-readable upstream context
  for that step.

  ### Thread and turn execution model

  For each step attempt:

  1. Load the referenced myteam role using the same loader path as
     myteam get role, but through a reusable internal capture helper
     that returns the printed instruction text.
  2. Start a fresh AppServer thread with:
      - base_instructions: captured role instructions
      - developer_instructions: fixed workflow-runner rules
      - workflow/step defaults applied as thread/start overrides
  3. Start exactly one turn on that thread with:
      - a single text input containing the step prompt plus
        serialized resolved inputs JSON
      - output_schema set to the step’s declared schema
  4. Subscribe to streamed notifications and track items for that
     turn_id
  5. Mark the step complete only when all of these are true:
      - a turn/completed notification arrives
      - the runner has captured the final completed AgentMessage for
        that turn
      - the final message parses as JSON
      - the parsed JSON validates against output_schema
  6. Publish that validated object as steps.<step_id> for downstream
     references and persist it to disk

  Do not reuse threads across steps.
  Do not use thread/fork in v1.
  Do not use semantic guesses, tool completion, or prose heuristics
  to decide step completion.

  Retry/resume rule:

  - if a step fails, interrupts, loses transport, or produces
    invalid output, the workflow pauses in failed
  - resume reruns the first incomplete step in a new fresh thread
    attempt using the same resolved inputs
  - previously successful steps are never rerun during ordinary
    resume

  ## Implementation Changes

  ### Framework refactor

  Create reusable internal components before adding the CLI surface:

  - instruction_loader helper that captures role/skill loader output
    instead of only printing it
  - workflow_definition parser/validator for YAML, duplicate step
    IDs, bad refs, and unsupported schema shapes
  - workflow_state persistence layer for run and step-attempt
    records
  - app_server_client abstraction for JSON-RPC over stdio so tests
    can fake the transport cleanly

  Use a standard JSON Schema validator dependency for local
  validation so workflow input and output checks do not rely only on
  model compliance.

  ### Feature addition

  Implement the runner loop around the existing AppServer protocol:

  - launch subprocess, initialize, then per-step thread/start and
    interrupted
    turn
  - persist state after every meaningful transition so runs are
    resumable

  Ship one documented example workflow definition that mirrors the
  meeting’s preferred staged development flow:

  - interface clarification
  - framework refactor plan
  - implementation design
  - test update plan
  - implementation
  - review

  ## Test Plan

  Add CLI and runner tests for these cases:

  - valid workflow YAML loads; duplicate IDs, invalid refs, and
    missing required fields fail deterministically
  - workflow run executes sequentially and stores thread_id,
    turn_id, and validated step outputs
  - downstream step input resolution uses only persisted structured
    outputs from prior steps
  - a completed turn without a final AgentMessage fails the step
  - invalid JSON or schema-mismatched final output fails the step
  - turn/failed, turn/interrupted, and transport loss persist a
    resumable failed state
  - workflow resume reruns only the first incomplete step in a fresh
    thread attempt
  - workflow status reports run status, current step, and prior
    successful outputs without mutating state

  ## Assumptions And Defaults

  - Scope is myteam only; no Codex AppServer protocol changes are
    planned
  - v1 is linear only; branching/state-machine workflows are
    deferred
  - schema-valid structured output is required for completion; there
    is no manual override in v1
  - the workflow system remains local and deterministic from
    myteam’s perspective: local YAML, local role loading, local run-
    state files, and a locally launched AppServer client session
  - the runner uses Codex notifications as the source of truth for
    turn lifecycle, but only persisted structured step outputs may
    feed later steps