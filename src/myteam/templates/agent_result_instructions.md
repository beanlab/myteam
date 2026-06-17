## Session result reporting

This session is part of a larger pipeline. The information needed from this session and how to report it are described here.

You call `myteam result` when you have finished the task and are ready to report the result. Pipe the result JSON to `myteam result`, e.g.: 

```bash
myteam result <<EOF
{"status": "done", "findings": "ready to merge"}
EOF
```

Do **not** call `myteam result` unless you are reporting the data described below, and do not report until you have finished the specified task.

The result JSON should follow this schema:

```json
{{ OUTPUT_SCHEMA_JSON }}
```
