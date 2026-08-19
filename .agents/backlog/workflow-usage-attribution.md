# Workflow usage attribution for resumed sessions

`SessionResult.usage` does not identify whether an agent runtime reported usage for the latest invocation or cumulatively for the complete native session. This makes resumed-session totals unreliable: summing cumulative snapshots double-counts prior work, while subtracting invocation-scoped values is incorrect.

Define an explicit usage scope in the framework/adapter contract, such as `invocation` or `session_total`. Preserve the raw runtime-reported values and have `myteam` derive invocation deltas only when the adapter guarantees cumulative monotonic counters. Account for model changes and counter resets rather than silently producing invalid deltas.

Workflow-level aggregation should consume attributed invocation usage while retaining the native session ID and raw usage snapshot for investigation. Update built-in adapters, public documentation, and resumed-session contract tests together.
