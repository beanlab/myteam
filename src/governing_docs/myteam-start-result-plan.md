# `myteam start` Explicit Workflow Result Plan

## Summary

`myteam start` should return **text intended for the caller**, not a replay of terminal display bytes.

Workflows should therefore report their caller-facing result through an explicit workflow-result API. Ordinary workflow stdout/stderr should be treated as live display/logging, not as the returned `myteam start` result.

This is intentionally a breaking change.

The desired layering is:

```text
supervisor
  └── workflow process
        └── run_agent(...)
              └── agent process
```

Results cross process boundaries explicitly:

```text
agent result:
  myteam result -> run_agent-owned agent result socket -> SessionResult.output

workflow result:
  workflow code/wrapper -> supervisor-owned workflow result socket -> myteam start output text
```

`myteam start` remains text-oriented. The explicit workflow result is not structured data from the supervisor's perspective; it is the exact text the workflow wants `myteam start` to print for its caller.

## 1. Design

### Goals

- Preserve the decision that `myteam start` returns **text**, because it is called by a human or AI agent through a terminal/shell interface.
- Prevent interactive agent subsession PTY/TUI output from being captured and replayed as workflow output.
- Make nested workflow behavior deterministic and robust.
- Avoid byte-level inference of which PTY output is a result versus terminal display.
- Avoid printing `null` for absent results.
- Keep `run_agent` responsible for agent-session result collection, and keep workflows responsible for deciding what text their own result should be.

### Non-goals

- `myteam start` should not return structured data as its API contract.
- `myteam result` should not report directly to the workflow supervisor.
- The supervisor should not scrape a workflow's PTY transcript to infer its returned result.
- This plan does not change the current decision to close agent sessions using their configured exit sequence, e.g. `/quit`.

### New workflow-result API

Add a public workflow API:

```python
from myteam.workflows import report_workflow_result
```

`report_workflow_result` appends text to the result that will be returned when the workflow exits. It does not end the workflow immediately, and it may be called multiple times.

Proposed signature:

```python
def report_workflow_result(text: str | None = None) -> None:
    """Append text to the result returned by the current managed workflow.

    Passing None reports no text. If no workflow result text is
    reported, `myteam start` prints nothing for the workflow result.
    """
```

Possible convenience helper:

```python
def report_workflow_json_result(value: Any | None) -> None:
    if value is not None:
        report_workflow_result(json.dumps(value) + "\n")
    else:
        report_workflow_result(None)
```

But the core API should be text-based.

### Result channel

The supervisor should accept workflow result reports over the existing supervisor RPC socket. This is intentionally separate from the `run_agent` agent-result socket, but it does not require another Unix socket because managed workflows already inherit:

```text
MYTEAM_MOTHERSHIP_SOCKET=/path/to/mothership.sock
MYTEAM_WORKFLOW_INVOCATION_ID=<workflow-request-id>
```

Workflow result messages should be small JSON RPC-style messages sent to the supervisor, for example:

```json
{
  "version": 1,
  "kind": "workflow_result",
  "request_id": "...",
  "text": "..."
}
```

A `null` text value appends no text.

The supervisor appends reported text for the workflow request. If the workflow calls `report_workflow_result` multiple times, the supervisor concatenates the non-None text values in call order.

### Semantics

#### `myteam start` output

When a workflow completes, the `myteam start` client prints only the workflow result text:

- if one or more non-empty text fragments were reported: print their concatenation exactly;
- if only empty strings were reported: print nothing;
- if `None` was reported: append no text;
- if no result text was ever reported: print nothing.

Errors are separate. If a workflow exits nonzero, the `myteam start` shim should still exit nonzero. The result text, if set, may still be printed; the workflow's diagnostic display/logs should have already appeared live while the workflow was active.

#### Workflow stdout/stderr

Workflow stdout/stderr are live display/log streams. They are not the returned result of `myteam start`.

This means Python workflow authors should use:

```python
print("progress/logging shown live")
report_workflow_result("final text returned to caller\n")
```

Instead of relying on `print(...)` as the returned result.

The supervisor may still record a display transcript for debugging, but this transcript must not be replayed as `myteam start` result text.

#### Markdown workflows

Markdown workflows are single-step wrappers around `run_agent`. The Markdown wrapper should call `run_agent(...)`, then report workflow result text derived from `SessionResult.output`.

Recommended behavior:

```python
result = run_agent(...)
if result.output is not None:
    report_workflow_result(json.dumps(result.output) + "\n")
else:
    report_workflow_result(None)
```

This means Markdown workflows print the reported agent output as text when there is one, and print nothing for `None`.

#### Python workflows

Python workflows are responsible for explicitly reporting their result text.

Example:

```python
from myteam import run_agent
from myteam.workflows import report_workflow_result


def main():
    step = run_agent(prompt="Investigate the issue", output={"summary": "..."})
    if step.output is None:
        report_workflow_result(None)
    else:
        report_workflow_result(f"Summary: {step.output['summary']}\n")


if __name__ == "__main__":
    main()
```

If a Python workflow never calls `report_workflow_result` with text, `myteam start` prints no result text.

#### Nested workflows

For nested workflows, the inner `myteam start` shim should:

1. request the child workflow from the supervisor;
2. wait for completion;
3. print the child workflow's explicit result text, if any;
4. exit with the child workflow's exit code.

The inner child workflow's interactive display is visible while the child is active, but it is not replayed into the parent session afterward.

#### Top-level workflows

For top-level workflows, the same rule applies: `myteam start` prints the explicit result text when the workflow completes.

Any live display/logging shown during the workflow should not be replayed from a PTY transcript. The final explicit result text may appear at completion even if stdout is a TTY, because it is the workflow's intended returned result.

### Relationship to `run_agent`

`run_agent` continues to own the agent result channel:

```text
myteam result -> MYTEAM_AGENT_SESSION_RESULT_SOCKET -> run_agent -> SessionResult
```

`run_agent` should not report workflow result text automatically. Workflow code decides what the workflow result text should be.

Markdown workflows are an exception only in the sense that their wrapper is workflow code supplied by `myteam`; that wrapper should report workflow result text from the single `run_agent` output.

### Terminal robustness implications

The explicit result design avoids using PTY transcripts as returned output. This should eliminate the duplicate/replayed Pi TUI blocks seen with nested sessions.

Additional terminal hygiene is still recommended:

- flush real terminal input on session switches and final restore to avoid stranded terminal query response bytes such as trailing `6c`;
- continue suppressing visible forwarding of post-result agent teardown bytes where appropriate;
- keep PTY display transcript recording separate from workflow result text.

## 2. Governing document changes

The following governing documents should be updated to reflect this decision.

### `src/governing_docs/scenarios/workflows/start.md`

Update the nested `myteam start` sections.

Current model says nested `myteam start` prints child stdout and stderr. Replace with:

- nested `myteam start` prints the child workflow's explicit result text;
- ordinary workflow stdout/stderr are live display/logging, not returned result text;
- child PTY/TUI display is not replayed to the parent after the child exits;
- if no workflow result was set or the result is `None`, nested `myteam start` prints nothing;
- nested `myteam start` exits with the child workflow's exit code.

Update the polling result payload examples. Instead of:

```json
{
  "exit-code": 0,
  "stdout": "hello world",
  "stderr": ""
}
```

Use something conceptually like:

```json
{
  "exit-code": 0,
  "result_text": "hello world\n"
}
```

or keep the implementation field named `stdout` only if the docs clearly state that it means explicit workflow result text, not captured process stdout. Prefer renaming to avoid ambiguity.

Clarify that the supervisor owns live PTY display and may record transcripts, but transcripts are not returned by `myteam start`.

### `src/governing_docs/scenarios/workflows/run-agent.md`

Add a short section explaining that `run_agent` returns `SessionResult` to workflow code only. It does not report workflow result text.

Clarify the layering:

```text
myteam result -> run_agent -> SessionResult -> workflow code -> report_workflow_result -> myteam start output
```

The `Reporting Agent Session Results` section should explicitly say that agent results are not automatically included in workflow output. Workflow authors choose if/how to include `SessionResult.output` in the workflow's explicit result text.

The Markdown workflow wrapper behavior should be referenced: Markdown workflows automatically convert the single `run_agent` output into explicit workflow result text.

### `src/governing_docs/scenarios/workflows/formats.md`

Update Python workflow examples to import and call `report_workflow_result`.

Old style:

```python
print(step2.output)
```

New style:

```python
report_workflow_result(json.dumps(step2.output) + "\n")
```

Document that `print(...)` is for live display/logging. It is not returned by `myteam start`.

Update Markdown workflow docs to say:

- Markdown body/frontmatter still maps to a single `run_agent` call;
- the wrapper sets the workflow result text to `json.dumps(result.output) + "\n"` when `result.output` is not `None`;
- if `result.output` is `None`, the Markdown workflow has no result text and `myteam start` prints nothing.

### `src/governing_docs/scenarios/workflows/workflows.md`

Add `report_workflow_result` to the overview of workflow concepts.

Define three separate streams/concepts:

1. agent result: structured data reported to `run_agent`;
2. workflow result: text explicitly returned by the workflow to `myteam start`;
3. live display/logging: terminal output shown while workflows and agents are active.

### `src/governing_docs/scenarios/workflows/usage.md`

Likely no required change unless examples mention returned workflow output. If updated, keep `UsageInfo` scoped to agent sessions and `SessionResult`, not workflow result text.

### `src/governing_docs/scenarios/workflows/configuration.md`

Likely no required change.

### `README.md`

Update workflow sections that describe `myteam start` behavior.

Required doc changes:

- `myteam start` prints explicit workflow result text, not captured stdout/stderr or PTY transcript;
- Python workflows should call `report_workflow_result` to return text to a caller;
- Markdown workflows report result text automatically from `run_agent` output;
- `None`/missing results print nothing;
- `print(...)` is live display/logging.

### Templates

Update built-in new workflow templates so new workflows demonstrate `report_workflow_result`.

Relevant template docs/code:

- `src/myteam/templates/new_workflow.py`
- `src/myteam/templates/new_workflow.md` if it describes output behavior
- `src/myteam/templates/workflow_markdown_wrapper.py`

## 3. Code changes

### Add workflow result protocol constants

File: `src/myteam/workflows/execution/protocol.py`

Add an RPC kind constant:

```python
KIND_WORKFLOW_RESULT = "workflow_result"
```

Workflow result reporting should use the existing supervisor socket from `MYTEAM_MOTHERSHIP_SOCKET` and the current workflow id from `MYTEAM_WORKFLOW_INVOCATION_ID`.

### Add workflow result API

New or existing file options:

- `src/myteam/workflows/workflow_result.py`
- or add to `src/myteam/workflows/results.py`

Recommended new file: `src/myteam/workflows/workflow_result.py`.

Implement:

```python
def report_workflow_result(text: str | None = None) -> None:
    socket_path = os.environ.get(ENV_SOCKET)
    request_id = os.environ.get(ENV_WORKFLOW_INVOCATION_ID)
    if not socket_path or not request_id:
        # Outside a managed workflow, this can either be a no-op or raise.
        # Recommended: raise RuntimeError to catch incorrect usage.
        raise RuntimeError("No active myteam workflow is available.")
    RpcClient(socket_path).call(KIND_WORKFLOW_RESULT, request_id=request_id, text=text)
```

Validation:

- `text` must be `str` or `None`;
- non-string values should raise `TypeError` so callers consciously serialize structured data to text.

Export it from:

- `src/myteam/workflows/__init__.py`
- `src/myteam/__init__.py` if desired for `from myteam import report_workflow_result`

### Extend supervisor request records

File: `src/myteam/workflows/execution/mothership.py`

Extend `RequestRecord`:

```python
workflow_result_parts: list[str] = field(default_factory=list)
```

Add handling for `KIND_WORKFLOW_RESULT` in `_handle_connection`:

```python
if kind == KIND_WORKFLOW_RESULT:
    response = self._report_workflow_result(message)
```

Implement validation:

- request id must be known;
- text must be `str` or `None`;
- probably allow result updates while request is pending/running only;
- `None` appends nothing; non-None strings are appended in call order.

Example:

```python
def _report_workflow_result(self, message: dict[str, Any]) -> dict[str, Any]:
    request_id = message.get("request_id")
    text = message.get("text")
    if not isinstance(request_id, str) or not request_id:
        raise ValueError("workflow_result requires request_id.")
    if text is not None and not isinstance(text, str):
        raise ValueError("workflow_result text must be a string or null.")
    record = self.requests.get(request_id)
    if record is None:
        raise ValueError("Unknown workflow request_id.")
    if text is not None:
        record.workflow_result_parts.append(text)
    return {"ok": True}
```

### Change workflow completion payload

File: `src/myteam/workflows/execution/mothership.py`

In `_handle_workflow_exit`, stop using `session.recording.snapshot()` as returned stdout.

Current problematic behavior:

```python
result = {
    "exit_code": exit_code,
    "stdout": _normalize_pty_text(session.recording.snapshot()),
    "stderr": session.stderr_snapshot(),
}
```

New behavior:

```python
record = self.requests.get(session.request_id)
result_text = ""
if record is not None:
    result_text = "".join(record.workflow_result_parts)

result = {
    "exit_code": exit_code,
    "result_text": result_text,
    "transcript": _normalize_pty_text(session.recording.snapshot()),
    "stderr_transcript": session.stderr_snapshot(),
}
```

If keeping `WorkflowProcessResult.stdout` for compatibility inside code, populate it from `result_text`, not transcript.

Important: workflow display/log stdout and stderr are no longer returned as `stdout`/`stderr` from `myteam start`.

### Change `WorkflowProcessResult`

File: `src/myteam/workflows/commands.py`

Current:

```python
@dataclass(frozen=True)
class WorkflowProcessResult:
    exit_code: int
    stdout: str
    stderr: str
```

Recommended:

```python
@dataclass(frozen=True)
class WorkflowProcessResult:
    exit_code: int
    result_text: str
```

Or, if minimizing internal churn:

```python
@dataclass(frozen=True)
class WorkflowProcessResult:
    exit_code: int
    stdout: str  # explicit workflow result text, not process stdout
    stderr: str = ""
```

Prefer renaming to `result_text` to avoid recreating ambiguity.

Update:

- `start_workflow(...)` to return `result.result_text`;
- `start_workflow_cli(...)` to print `result.result_text` only if non-empty;
- `_workflow_process_result_from_supervisor_result(...)` to read `result_text` from the supervisor payload;
- nested `myteam start` behavior to print only `result_text`.

### Update Markdown workflow wrapper

File: `src/myteam/templates/workflow_markdown_wrapper.py`

Current behavior prints `json.dumps(result.output)` to stdout.

Change to use explicit workflow result:

```python
from myteam.workflows import run_agent, report_workflow_result

...
result = run_agent(...)
if result.output is not None:
    report_workflow_result(json.dumps(result.output) + "\n")
else:
    report_workflow_result(None)
```

Do not print `null`.

### Update templates

File: `src/myteam/templates/new_workflow.py`

Update example to demonstrate explicit result:

```python
from myteam import run_agent
from myteam.workflows import report_workflow_result


def main():
    result = run_agent(prompt="Not implemented yet. Tell the user.")
    if result.output is not None:
        report_workflow_result(json.dumps(result.output) + "\n")
```

Or simply:

```python
report_workflow_result("Not implemented yet.\n")
```

depending on desired starter behavior.

### Keep `run_agent` out-of-band result handling

File: `src/myteam/workflows/agent_session.py`

No conceptual change to agent result semantics:

- agent sessions report through `MYTEAM_AGENT_SESSION_RESULT_SOCKET`;
- `run_agent` returns `SessionResult`;
- agent PTY/TUI display should not become workflow result text.

The recent shared PTY forwarding and post-result visible suppression work remains useful.

### Terminal input flushing

Files:

- `src/myteam/workflows/execution/terminal.py`
- `src/myteam/workflows/execution/mothership.py`

Add a method:

```python
def flush_input(self) -> None:
    if self.stdin_fd is not None:
        try:
            termios.tcflush(self.stdin_fd, termios.TCIFLUSH)
        except OSError:
            pass
```

Call it:

- before suspending a parent workflow;
- after child workflow exit before resuming parent;
- before final terminal restore/return to shell;
- possibly after terminal clear on session switch.

This addresses trailing terminal response bytes such as `6c` and bells leaking into the next active process or shell prompt.

### Tests to add/update

Add tests covering the new semantics.

#### Markdown workflow result text

- fake agent reports `{"foo": "wootage"}`;
- `myteam start markdown.md` returns/prints exactly `{"foo": "wootage"}\n`;
- PTY transcript/display text from the agent is not included.

#### Markdown `None` result

- fake agent exits cleanly without `myteam result`;
- wrapper reports no result text;
- `myteam start` prints nothing.

#### Python explicit result

Workflow:

```python
from myteam.workflows import report_workflow_result
print("live log")
report_workflow_result("final result\n")
```

Expected:

- live transcript may contain `live log`;
- `myteam start` result text is only `final result\n`.

#### Python no result

Workflow prints text but never calls `report_workflow_result`.

Expected after breaking change:

- `myteam start` result text is empty;
- exit code reflects process exit.

#### Nested workflow no TUI replay

- parent workflow invokes nested `myteam start`;
- child workflow runs a fake TUI-ish agent that emits control-looking text and reports a result;
- parent observes only the child explicit result text from the nested `myteam start`, not the child's display transcript.

#### Multiple result sets

- workflow calls `report_workflow_result("first\n")`, then `report_workflow_result("second\n")`;
- result is `first\nsecond\n`.

#### Invalid usage

- calling `report_workflow_result` outside a managed workflow raises `RuntimeError`;
- passing a non-string/non-None value raises `TypeError` or returns a friendly error.

## Implementation order

1. Add protocol constant and `report_workflow_result` API.
2. Extend `Mothership` RPC handling and request records for explicit result text.
3. Change workflow completion payload to use explicit result text instead of PTY transcript.
4. Update `commands.py` to print/return `result_text`.
5. Update Markdown wrapper to call `report_workflow_result` and stop printing `null`.
6. Update templates and exports.
7. Add terminal input flushing around session switches.
8. Update tests.
9. Update governing docs and README.

## Decisions and open questions

Decisions:

- API name: `report_workflow_result`.
- Multiple calls concatenate in call order.
- `report_workflow_result(None)` appends no text.

Open questions:

- Whether workflow result text should be accepted only as `str | None`, or whether bytes should also be allowed. Recommendation: only `str | None`.
- Whether top-level `myteam start` should always print explicit result text even in interactive mode. Recommendation: yes, because it is intentionally the workflow's returned text.
- Whether display transcripts should be exposed in debug logs/artifacts. Recommendation: keep internally available but do not print by default.
