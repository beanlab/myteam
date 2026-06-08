# Starting Workflows

`myteam start <workflow>` starts a workflow.

If the user runs this command from the terminal, a new managed-session engine is created.

When `myteam start` is invoked in a child process under the managed-session, the parent session pauses while the new workflow is run; the output of the child workflow is returned to the parent which then resumes. 

Thus, the parent agent session experiences the child workflow much like a tool call. But the child session has full TTY interactivity with the user as if it were the parent session. 

If `myteam start` is invoked in an unmanaged agent session (e.g. the user ran `codex` directly in the terminal), an error will be raised.

