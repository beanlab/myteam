# Resolves Agent Config

## Purpose

Select runtime behavior.

---

# Context

A workflow step starts an agent by name. The project may provide an optional
local override at `.myteam/.config/<agent>.py`, and the installed package may
provide a built-in default config for the same agent.

---

# Action

The workflow runtime resolves the agent config before starting the agent.

---

# Interaction

| Action | Outcome |
| --- | --- |
| No local override exists for the requested agent | The runtime logs that no local override was found and uses the packaged default config when one exists. |
| A local override exists and provides a valid config | The runtime uses the local override for that agent. |
| A local override cannot be loaded | The runtime logs the load failure and falls back to the packaged default config when one exists. |
| A local override loads but is invalid | The runtime logs the validation failure and falls back to the packaged default config when one exists. |
| No valid local or packaged config exists | The runtime reports a useful config resolution failure. |

---

# Outcome

Agent-specific runtime settings are resolved from a project-local override when
the override is valid, otherwise from the packaged default when available. The
runtime explains missing local files, load errors, invalid configs, fallback
decisions, and unrecoverable resolution failures through operator-visible
logging or error output.

---

# Related Scenarios

- `src/governing_docs/scenarios/workflow/agent_runtime_configs/discovers_codex_session_from_recent_nonce.md`
- `src/governing_docs/scenarios/workflow/agent_runtime_configs/does_not_create_project_config.md`
