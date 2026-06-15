## Session result reporting

This session is part of a larger pipeline. The information needed from this session and how to report it are described here.

When you have the requested information, pipe the final result JSON to `myteam result`.

Example:

```bash
myteam result <<EOF
{"status": "done", "findings": "ready to merge"}
EOF
```

The result JSON should follow this schema:

```json
{{ OUTPUT_SCHEMA_JSON }}
```
