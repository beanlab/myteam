# Locating the Active Workflow

`myteam where` prints the complete active `myteam start` hierarchy, oldest to current, with one entry per line and two spaces of indentation per nesting level.

Workflow entries contain only their absolute, resolved workflow path. Agent-session entries use:

```text
name (agent=agent-type, model=model-name, session_id=native-id)
```

`model` and `session_id` are omitted when unavailable.

The hierarchy contains only running workflows, suspended workflow ancestors, and active agent sessions. Completed entries are absent. Workflow code between agent sessions therefore shows only workflow entries. A workflow started directly by workflow code may appear beneath its parent workflow without an intervening agent entry; a workflow started by an agent appears beneath that agent.

All displayed values escape Unicode control characters so each entry occupies one physical line.

The command accepts no arguments or options other than standard `-h`/`--help`. It has no JSON mode. Outside a process managed by `myteam start`, it exits nonzero and explains that requirement. An agent session created by standalone `run_agent` does not qualify. An unreachable supervisor, malformed response, incomplete snapshot, or invalid hierarchy produces one concise diagnostic, a nonzero exit, and no partial stdout.
