# Workflow Alignment Plan

The governing docs now describe two separate layers:

1. **`myteam start`** = workflow/process supervision and TTY multiplexing.
2. **`run_agent`** = agent-session management inside a workflow, including prompt rendering, result socket, nonce/session lookup, transcript, usage, and `SessionResult`.

The code currently still blends these together: `run_agent` delegates agent session launching to the `Mothership` supervisor over the same socket used by `myteam start`, and `myteam result` reports to that same supervisor. That is the main architectural mismatch.

## Biggest architectural change: split supervisor concerns from agent-session concerns

### Current code

In `src/myteam/workflows/commands.py`, `run_agent(...)`:

- requires `ENV_SOCKET`;
- calls the `Mothership` with `KIND_START_AGENT_SESSION`;
- waits for a result via supervisor polling.

In `src/myteam/workflows/execution/mothership.py`, the supervisor:

- starts workflows;
- starts agent sessions;
- owns result reporting for agents;
- resolves agent session metadata and usage.

So the supervisor currently manages both workflows and agents.

### New docs

The docs say:

- `myteam start` owns the **workflow supervisor socket**.
- `run_agent` owns a **separate per-agent-session result socket**.
- `myteam result` should report to the `run_agent` socket, not the supervisor socket.
- The supervisor only coordinates workflow process trees and terminal handoff.

### Code work needed

Split this into two execution subsystems.

#### `myteam start` / supervisor subsystem

Likely files/modules:

- `src/myteam/workflows/execution/mothership.py`
- `src/myteam/workflows/execution/protocol.py`
- `src/myteam/workflows/commands.py`

Responsibilities:

- start workflow processes;
- forward terminal to active workflow;
- suspend/resume workflow process groups;
- support nested `myteam start`;
- store nested workflow stdout/stderr/exit code by workflow request id;
- expose only workflow-control RPCs.

It should probably **remove**:

- `KIND_START_AGENT_SESSION`;
- agent-specific env vars from the supervisor protocol;
- agent usage/session lookup from `Mothership`;
- `StartAgentSessionCommand`;
- `_start_agent_session`;
- `_launch_agent_session`;
- `_session_result_payload` as an agent concern.

#### `run_agent` subsystem

Probably new module, e.g.:

- `src/myteam/workflows/agent_session.py`
- or `src/myteam/workflows/run_agent.py`

Responsibilities:

- render prompt with Jinja2 and `input`;
- generate nonce;
- start a local result socket for `myteam result`;
- launch the configured agent CLI;
- pass result-socket env vars to the agent session;
- record transcript;
- send exit sequence after result is received;
- detect clean quit with no result as `output=None`;
- locate native agent session data by nonce;
- collect usage;
- return `SessionResult`.

`myteam result` in `src/myteam/workflows/results.py` should connect to this new result socket, not the supervisor socket.

## `myteam start` currently does not match the new TTY/process model

### Current code

Top-level workflow start in `Mothership` uses:

```python
subprocess.run(
    command.argv,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)
```

inside `_run_workflow_process`.

That means workflow processes are not the active PTY-backed child session. Their stdout/stderr are captured silently until completion. Only agent sessions launched through the supervisor become PTY-backed active sessions.

### New docs

The supervisor should own the user’s terminal and forward it to the **active workflow process tree**.

Runtime shape should be:

```text
user terminal <-> supervisor <-> active child workflow PTY
```

When nested `myteam start` happens, the supervisor should suspend the **whole parent workflow process group**, not just the active agent.

### Code work needed

`Mothership` should launch workflows as managed PTY/process-group sessions, not as background `subprocess.run(... PIPE ...)` threads.

Likely changes:

- reuse/adapt `ManagedPtyProcess` for workflow processes;
- make workflow processes, not agent sessions, the primary `active`/`stack` objects;
- suspend/resume workflow process groups on nested starts;
- forward terminal input/output to active workflow PTY;
- capture workflow output for nested `myteam start` result delivery;
- remove the current agent-session stack behavior from `Mothership`.

This is the core implementation change needed to align with `start.md`.

## `myteam result` needs to report to `run_agent`, not to `Mothership`

### Current code

`src/myteam/workflows/results.py` uses:

```python
ENV_SOCKET
ENV_SESSION_ID
ENV_REQUEST_ID
KIND_REPORT_RESULT
```

Those are supervisor concepts.

### New docs

`run_agent` should expose something conceptually like:

```text
MYTEAM_AGENT_SESSION_RESULT_SOCKET=/path/to/socket
MYTEAM_AGENT_SESSION_NONCE=<nonce>
```

Then `myteam result` sends JSON to that socket.

### Code work needed

Add separate env vars in `protocol.py` or a new module, e.g.:

```python
ENV_AGENT_SESSION_RESULT_SOCKET = "MYTEAM_AGENT_SESSION_RESULT_SOCKET"
ENV_AGENT_SESSION_NONCE = "MYTEAM_AGENT_SESSION_NONCE"
```

Then update `report_result` to:

- require the agent result socket;
- send output JSON to that socket;
- error cleanly outside a managed `run_agent` session.

The supervisor socket should no longer be involved in agent result reporting.

## `SessionResult` is missing fields from the docs

### Docs

`SessionResult` should include:

```python
class SessionResult:
    exit_code: int
    output: dict[str, Any] | None
    usage: list[UsageInfo]
    session_id: str
    transcript: str
```

### Current code

`src/myteam/workflows/results.py`:

```python
@dataclass
class SessionResult:
    output: dict[str, Any] | None
    usage: list[UsageInfo]
    transcript: str
    session_id: str | None = None
```

Missing:

- `exit_code`.

### Code work needed

Add `exit_code` to `SessionResult`, update:

- `to_jsonable`;
- `_session_result_from_payload`;
- markdown workflow wrapper;
- any tests around session result payloads.

Also decide whether `session_id` can be `None` for clean/error cases. Docs say `str`, but implementation probably needs `str | None` until lookup succeeds/fails.

## Prompt rendering is not aligned

### Docs

`run_agent` renders the prompt using Jinja2:

```python
session_prompt = jinja.render(prompt, **input)
```

### Current code

`run_agent` does not render the prompt with `input`.

Markdown workflows in `src/myteam/templates/workflow_markdown_wrapper.py` do this instead:

```python
prompt = content.format(**input_values) if input_values else content
```

That is both in the wrong layer and the wrong template language.

### Code work needed

- Add `jinja2` to `pyproject.toml`.
- Move prompt rendering into `run_agent`.
- Use Jinja2, not `str.format`.
- Markdown workflow wrapper should pass raw markdown body as `prompt` and parsed `--input` as `input`.

Also, `_build_agent_prompt` currently only appends session/result instructions when `output_schema` is not `None`. But docs say the nonce is always needed for session lookup. So nonce metadata should be appended even when no output schema is provided.

## Agent config protocol is close but not quite aligned

### Docs

Agent config protocol:

```python
class AgentConfig(Protocol):
    def build_argv(
        self,
        prompt_text: str,
        model: str | None,
        reasoning: str | None,
        interactive: bool,
        session_id: str | None,
        fork: bool,
        extra_args: tuple[str, ...] | None
    ) -> list[str]

    def get_exit_sequence(self) -> bytes
    def locate_session_data(self, nonce: str, context: AgentSessionContext) -> Any
    def get_session_id(self, session_data: Any) -> str
    def get_usage_info(self, session_data: Any) -> list[UsageInfo]
```

### Current code

`src/myteam/workflows/agents/runtime.py` supports parts of this but has old/internal shape:

- `AgentRuntimeConfig.get_session_info(nonce) -> tuple[str, Path]`;
- `get_usage_info(session_path) -> UsageInfo | None`;
- `build_argv` wrapper has argument order from old design;
- `AgentSessionContext` field is `home`, with `user_home` as a property;
- `_require_agent_name` requires `.isidentifier()`, so a configured agent like `codex-mini` from the docs is rejected.

### Code work needed

- Make the documented `AgentConfig` protocol the main contract.
- Support arbitrary custom agent names from `.myteam.yaml`, including hyphenated names.
- Stop coercing session data to `Path`; docs allow `Any`.
- Let `get_usage_info` return `list[UsageInfo]`, not only one `UsageInfo | None`.
- Update built-in `codex` and `pi` configs to match the documented method signatures.
- Decide whether to keep legacy module-level config compatibility as a shim.

## `.myteam.yaml` defaults are not actually wired through

### Docs

`.myteam.yaml` supports:

```yaml
defaults:
  agent: myagent
  model: gpt-5.4-nano
agents:
  myagent: agents/myagent.py::MyAgentConfig
```

### Current code

Agent lookup partially supports `.myteam.yaml` `agents`.

But defaults are not loaded from `.myteam.yaml` by `run_agent` or markdown workflows.

There is also `src/myteam/config.py`, but it defines:

```python
CONFIG_FILENAME = ".config.yaml"
```

and seems to represent an older `.myteam/.config.yaml` design.

### Code work needed

- Replace/repurpose `config.py` around `.myteam.yaml`.
- Load defaults from the current working directory.
- Apply defaults in `run_agent`, not just markdown workflows.
- Include `reasoning`.
- Decide whether legacy `.myteam/.config.yaml` fallback should remain.

## Markdown workflow wrapper needs changes

Current file:

`src/myteam/templates/workflow_markdown_wrapper.py`

Issues:

1. Uses `str.format`, not Jinja2.
2. Does rendering before `run_agent`, but docs put rendering in `run_agent`.
3. Does not load `.myteam.yaml` defaults.
4. Prints full `SessionResult` JSON unconditionally.
5. Treats output schema only if it is a dict.
6. Uses `resolve_agent_settings(frontmatter)` but no command-line overrides yet.

Docs say markdown workflow frontmatter maps to `run_agent` arguments, with body as prompt and `--input` as input.

Code work needed:

- parse frontmatter;
- separate `input` schema from actual `--input` value;
- pass body as `prompt`;
- pass `input_values` as `input`;
- pass `output` schema;
- pass agent/model/reasoning/interactive/session/fork/extra_args fields;
- allow CLI overrides for agent/model/reasoning/interactive if desired from `todo.md`;
- decide what the wrapper should print as workflow stdout.

## `myteam start` output behavior is old-design-ish

### Current code

`start_workflow_cli` eventually calls:

```python
_print_session_result(result)
```

which prints usage to stderr and `result.output` to stdout.

That treats a workflow invocation as if it returns a `SessionResult`.

### Docs

Python workflows can print anything. Markdown workflows are single-step workflows that call `run_agent`, but `myteam start` itself should behave as a workflow/process launcher.

For nested `myteam start`, docs say the client/shim prints the child workflow’s stdout and stderr to its own stdout/stderr and exits with the child status.

### Code work needed

Refactor `start_workflow_cli` so nested and top-level behavior follows the workflow-result format:

```json
{
  "exit-code": 0,
  "stdout": "...",
  "stderr": "..."
}
```

Internally the supervisor should store that result by workflow id. The nested shim should retrieve it, print stdout/stderr, and exit with the stored exit code.

The top-level invocation probably should not wrap workflow output as `SessionResult` JSON.

## Python workflow invocation should probably stop injecting `--input`

Current `_build_workflow_argv`:

```python
if suffix == ".py":
    argv = [sys.executable, absolute]
    if workflow_input_json is not None:
        argv.extend(["--input", workflow_input_json])
    argv.extend(args)
```

Docs say Python workflows can have any arguments they want, described in the frontmatter `usage` field. The generic `--input` argument is described specifically for Markdown workflows.

So this may need to become:

```python
[sys.executable, absolute, *args]
```

For Markdown workflows, keep `--input`/input JSON behavior.

## `myteam start` should stop falling back to arbitrary shell/default command

Current `_build_workflow_argv`:

```python
if target is None:
    default_command = os.environ.get("MYTEAM_DEFAULT_WORKFLOW_COMMAND") or os.environ.get("SHELL") or "sh"
    return shlex.split(default_command)
```

Docs do not describe `myteam start` with no workflow as a shell launcher. That seems old-design behavior.

Code work needed:

- require a workflow argument;
- error clearly if missing;
- error if target does not exist;
- error on unsupported extension;
- probably validate `type: workflow` frontmatter for `.md` and `.py`.

## Listing/skills mostly align, with some small mismatches

### `src/myteam/listing.py`

Mostly aligned.

Small mismatches:

- Folder header currently prints:

  ```text
  ----folder: agents/foo/----
  ```

  Docs example shows:

  ```text
  ----agents/foo/----
  ```

- Missing prefix currently errors with `Not a directory: ...`; docs suggest `Not a skill folder: nonsense`.

Not critical architecturally, but worth aligning.

### `src/myteam/skills.py`

Mostly aligned, but one important mismatch:

Docs say Python skills inherit working directory.

Current code runs Python skills with:

```python
cwd=skill_file.parent
```

That should probably be removed so the cwd is inherited from the caller.

## Templates/docs-facing text need updates

Files to revisit:

- `src/myteam/templates/agent_result_instructions.md`
- `src/myteam/templates/explain_resources.md`
- `src/myteam/templates/new_workflow.md`
- missing `src/myteam/templates/new_workflow.py`

Specific issues:

- result instructions should refer to the new run-agent result socket semantics only implicitly;
- nonce should be included even with no output schema;
- `new_workflow.py` is missing as an actual template file;
- explain text is close, but should match the new distinction between “start a workflow” and “report a run_agent result”.

## Tests likely need a large rewrite

The tests still appear to include old concepts like `tasks`, old agent config naming, and old supervisor-owned agent sessions.

Examples:

- `tests/test_agent_runtime_config.py` imports `myteam.tasks...`;
- current source is under `myteam.workflows...`;
- existing tests around `Mothership` assert old agent-session result behavior.

The new test shape should probably cover:

1. `run_agent` prompt rendering and result socket behavior.
2. `myteam result` outside managed session errors.
3. `myteam result` inside managed session reports output.
4. clean agent quit returns `SessionResult(output=None, exit_code=0)`.
5. nonzero agent exit returns/raises as intended.
6. top-level `myteam start` starts a workflow process under supervisor.
7. nested `myteam start` contacts existing supervisor.
8. supervisor suspends/resumes workflow process groups.
9. markdown workflow maps frontmatter/body/input to `run_agent`.
10. `.myteam.yaml` defaults and custom agents work.

## Suggested implementation order

1. **Define final protocols/data models** — **completed**
   - Added `SessionResult.exit_code` and included it in JSON serialization/deserialization.
   - Added agent-session result environment variable names for the future `run_agent` result socket.
   - Added `.myteam.yaml` loading for `defaults` and `agents`.
   - Added `reasoning` to workflow defaults.
   - Loosened local/custom agent-name resolution so configured names like `codex-mini` can resolve from `.myteam.yaml`.
   - Added focused tests for session-result payloads, `.myteam.yaml` parsing, and hyphenated configured agents.

2. **Build standalone `run_agent` implementation** — **mostly completed**
   - **Completed:** added a standalone per-`run_agent` agent result channel in `src/myteam/workflows/agent_result_channel.py`.
   - **Completed:** updated `myteam result` to require `MYTEAM_AGENT_SESSION_RESULT_SOCKET` and report to the new channel.
   - **Completed:** removed fallback result reporting to the old supervisor socket.
   - **Completed:** added focused tests for direct channel reporting, `myteam result` JSON/stdin/text handling, and unmanaged-session errors.
   - **Completed:** added `src/myteam/workflows/agent_session.py` as a standalone `run_agent` session runner.
   - **Completed:** changed `run_agent` to launch/manage agent processes directly instead of calling the supervisor's `KIND_START_AGENT_SESSION` RPC.
   - **Completed:** `run_agent` no longer requires `MYTEAM_MOTHERSHIP_SOCKET`.
   - **Completed:** `run_agent` now owns an `AgentResultServer` and injects `MYTEAM_AGENT_SESSION_RESULT_SOCKET` and `MYTEAM_AGENT_SESSION_NONCE` into the child agent environment.
   - **Completed:** prompt rendering now uses Jinja2 inputs before appending nonce/result instructions.
   - **Completed:** standalone `run_agent` resolves native session id and usage through the agent runtime config after child completion.
   - **Completed:** added focused tests for reported output, clean no-result exit, nonzero no-result exit, text result wrapping, Jinja rendering, supervisor independence, and child `myteam result` reporting.
   - **Completed:** removed supervisor agent-session RPC/dead code from `Mothership` and protocol, including the old `start_agent_session` and supervisor `report_result` paths.
   - **Completed:** added focused workflow-only supervisor tests.
   - Remaining: improve standalone TTY/transcript behavior from simple pipe forwarding to the final PTY/terminal model.

3. **Refactor `Mothership` to manage workflows only** — **partially completed**
   - **Completed:** removed agent-session RPCs and result-reporting responsibility.
   - Remaining: launch workflow PTY/process groups.
   - Remaining: nested start request/poll/ack with proper workflow process suspension.
   - Remaining: suspend/resume workflow process groups.

4. **Fix `myteam start` CLI behavior** — **completed for process-result semantics**
   - **Completed:** removed no-target fallback to `$MYTEAM_DEFAULT_WORKFLOW_COMMAND`, `$SHELL`, or `sh`; `myteam start` now requires a workflow file.
   - **Completed:** removed `SessionResult` wrapping from workflow start results.
   - **Completed:** introduced distinct workflow process-result semantics: `exit_code`, `stdout`, and `stderr`.
   - **Completed:** `Mothership` now preserves workflow stdout/stderr verbatim and no longer parses the last stdout line as JSON.
   - **Completed:** `start_workflow_cli` prints workflow stdout/stderr and exits nonzero when the workflow exits nonzero.
   - **Completed:** Python workflows no longer receive generic `--input`; only Markdown workflow wrapper invocation receives the input JSON.
   - **Completed:** added focused tests for missing target errors, Python/Markdown argv construction, stdout preservation, stderr preservation, and exit-code propagation.
   - Remaining: nested shim behavior is semantically aligned through shared process-result handling, but full nested interactive suspension/resume still awaits the workflow PTY/process-group supervisor work.

5. **Fix markdown workflow wrapper** — **completed**
   - **Completed:** wrapper passes the Markdown body directly as the `run_agent` prompt without `str.format` pre-rendering.
   - **Completed:** wrapper passes actual `--input` JSON values to `run_agent` regardless of whether an input schema is present.
   - **Completed:** Jinja rendering is delegated to `run_agent`.
   - **Completed:** frontmatter agent settings are passed through with `resolve_agent_settings`.
   - **Completed:** wrapper prints `result.output` as workflow stdout, not the full `SessionResult`.
   - **Completed:** wrapper prints `null` for no reported output.
   - **Completed:** added focused tests for prompt/input pass-through, frontmatter settings, clean output printing, `null` output, and non-object input validation.

6. **Clean smaller docs mismatches** — **completed**
   - **Completed:** Python skills now inherit the caller's working directory instead of running from the skill file's parent directory.
   - **Completed:** folder listing headers now match the docs (`----agents/foo/----`) instead of using `folder:`.
   - **Completed:** missing or non-directory list prefixes now report `Not a skill folder: ...`.
   - **Completed:** added a packaged `new_workflow.py` template and removed the inline fallback template.
   - **Completed:** `myteam new workflow foo.py` now uses the packaged Python workflow template.
   - **Completed:** added focused tests for Python skill cwd inheritance, listing folder headers, listing prefix errors, and Python workflow template creation.

## Short version

The code has some pieces that can be reused, especially PTY handling, terminal forwarding, frontmatter parsing, and agent config lookup. But the main workflow runtime needs to be inverted: **the supervisor should manage workflow processes; `run_agent` should manage agent processes.** Right now the supervisor manages both, which is the old design the new docs are trying to move away from.
