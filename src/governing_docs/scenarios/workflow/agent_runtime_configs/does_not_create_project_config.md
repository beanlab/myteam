# Does Not Create Project Config

## Purpose

Avoid project writes.

---

# Context

A project uses workflow agents but does not provide `.myteam/.config/` runtime
config files.

---

# Action

The workflow runtime resolves and starts a supported built-in agent.

---

# Outcome

The runtime uses packaged default agent configs without creating
`.myteam/.config/` or any `.myteam/.config/<agent>.py` files in the project.
Project-local config files are treated only as optional overrides supplied by
the project.

---

# Related Scenarios

- `src/governing_docs/scenarios/workflow/agent_runtime_configs/resolves_agent_config.md`
