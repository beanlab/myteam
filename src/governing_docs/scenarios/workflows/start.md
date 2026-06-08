# Starting Workflows

`myteam start <workflow>` starts a workflow.

## Managed Sessions

If the user runs this command from the terminal, a new managed-session engine is created.

A managed session is an agent TTY session started by `myteam`. The stdout/stderr of the session is recorded, and the session will be closed automatically when the agent calls `myteam result`.

When `myteam start` is invoked in a child process under a managed-session, the parent session pauses while the new workflow is run; the output of the child workflow is returned to the parent which then resumes, much like the callstack in canonical code flow. 

Thus, the parent agent session experiences the child workflow much like a tool call. But the child session has full TTY interactivity with the user as if it were the parent session. 

If `myteam start` is invoked in an unmanaged agent session (e.g. the user ran `codex` directly in the terminal), an error will be raised.

## Input

`myteam start <workflow> [--input <input JSON>]`

You can supply input to workflows that define an input schema using the `--input` flag. 

## Output

When a `myteam start` process completes, it will print the JSON output of the workflow on the last line of stdout. 

It will print the usage information of the workflow to stderr. 

## Usage

Markdown workflows or Python workflows using the `@workflow` decorator will display usage information to stderr. 

This will display aggregated usage by model and total cost. 

If machine-readable usage information is needed, write a custom Python workflow. 


