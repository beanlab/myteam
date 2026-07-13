## Session result reporting

This session is part of a larger pipeline. The information needed from this session and how to report it are described here.

You call `myteam result` when you have finished the task and are ready to report the result. Do **not** call `myteam result` unless you are reporting the data described below, and do not report until you have finished the specified task.

If `myteam result` rejects malformed JSON, fix the JSON and call `myteam result` again. The session is not complete until `myteam result` accepts valid JSON.

YOU MUST report your result with `myteam result` or the orchestration framework will not pick it up.

Pipe valid JSON to `myteam result` using HEREDOC syntax.
For example, if this were the schema you were given:

```yaml
status: (str) done, pending, or error
findings: (str) whether the branch is ready to merge or a description of remaining issues
```

Then you would report with a bash command like this:

```bash
myteam result <<EOF
{"status": "done", "findings": "ready to merge"}
EOF
```

Pay attention and be sure to do a shell command tool call and not just output the payload.

The result JSON for this session **must** follow this schema:

```json
{{ OUTPUT_SCHEMA_JSON }}
```
