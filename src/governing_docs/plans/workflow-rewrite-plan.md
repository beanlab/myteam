# Workflow Rewrite Plan

## Goal

Rewrite the codebase so the public center of gravity is `run_agent(...)` and the tty-backed session runtime it uses.

Resource listing / discovery has already been reworked and is considered stable. That area is no longer the focus of this plan unless later changes require small compatibility fixes.

We are **not** removing the recursive child-session behavior. The following must remain in the new design:

- parent/child session suspension and resumption
- session nonce injection
- out-of-band result delivery through sockets
- the env-var / session-registry plumbing used to let child sessions communicate back to the active parent process
- the ability to resume or fork existing agent sessions

What is going away is the YAML workflow / multi-step task engine layered on top of that runtime.

---

## Architectural Summary

### Keep
- the PTY-backed agent session transport
- structured result delivery through the result channel
- session discovery and session-id lookup
- recursive child session handling
- agent adapter resolution (`codex`, `pi`, and local overrides)
- skills, explain, and resource discovery
- usage aggregation / reporting
- resource listing/discovery behavior as already implemented

### Remove
- YAML task/workflow orchestration
- step-by-step task engines
- `$step.path` reference resolution
- child-task orchestration layers that are separate from the session recursion protocol
- task-specific schemas and validation models

### Rewrite
- implement `run_agent` as the primary workflow/session execution API
- ensure workflow Markdown handling just renders prompt text and calls `run_agent`, with optional flags supplied from Markdown frontmatter
- ensure CLI wiring exposes the right public commands and no legacy task surface area

---

## File-by-File Map

### `src/myteam/` core package

| File | Action               | Notes                                                                                                                                             |
|---|----------------------|---------------------------------------------------------------------------------------------------------------------------------------------------|
| `src/myteam/__init__.py` | Keep                 | Version resolution is still useful.                                                                                                               |
| `src/myteam/__main__.py` | Keep                 | Entry point stays.                                                                                                                                |
| `src/myteam/cli.py` | Rewrite              | Rewire the CLI to the simplified command set; remove legacy task plumbing.                                                                        |
| `src/myteam/commands.py` | Keep / minor rewrite | Keep `version` and `changelog`; adjust only if command names or docs change.                                                                      |
| `src/myteam/listing.py` | Keep                 | Resource listing has already been refactored and is working as desired.                                                                           |
| `src/myteam/frontmatter.py` | Keep                 | Frontmatter parsing is still needed for skills/workflows.                                                                                         |
| `src/myteam/skills.py` | Keep                 | Skill load/new behavior is already refactored.                                                                                                    |
| `src/myteam/disclosure/__init__.py` | Delete               | This currently mixes old task/role semantics with resource discovery. All that was useful here has already been moved to the refactored location. |
| `src/myteam/upgrade.py` | Keep                 | Not part of the workflow rewrite.                                                                                                                 |

### Workflow-facing API

| File | Action | Notes |
|---|---|---|
| `src/myteam/workflows/__init__.py` | Rewrite | This should become the public workflow API package, not a thin alias to task internals. |
| `src/myteam/workflows/commands.py` | Rewrite | Should expose the public `run_agent` surface and any helper functions needed for workflow defaults / agent settings. |
| `src/myteam/workflows/results.py` | Rewrite | Replace task result re-exports with the new workflow/session result types (`SessionResult`, `UsageInfo`). |
| `src/myteam/workflows/execution/__init__.py` | Rewrite or delete | Keep only if it is still the public entrypoint namespace. Otherwise collapse the functionality upward. |
| `src/myteam/workflows/agents/__init__.py` | Keep / rewrite | Re-export agent runtime helpers. |
| `src/myteam/workflows/agents/registry.py` | Keep / minor rewrite | Default agent selection and compatibility lookup stay. |
| `src/myteam/workflows/agents/runtime.py` | Keep / minor rewrite | This is core adapter-loading logic and should survive, but any task-specific naming should be removed. |
| `src/myteam/workflows/agents/codex.py` | Keep | Built-in Codex adapter stays. |
| `src/myteam/workflows/agents/pi.py` | Keep | Built-in Pi adapter stays. |
| `src/myteam/workflows/agents/agent_utils.py` | Keep | Shared terminal encoding and session-file helpers stay. |

### Session runtime / tty transport

| File | Action | Notes |
|---|---|---|
| `src/myteam/tasks/terminal/__init__.py` | Keep / rewrite | Package name can stay for now, but the docs and naming should become workflow/session oriented. |
| `src/myteam/tasks/terminal/pty_session.py` | Keep | Core PTY transport. Must stay. |
| `src/myteam/tasks/terminal/recording.py` | Keep | Transcript recording stays. |
| `src/myteam/tasks/terminal/result_channel.py` | Keep | Out-of-band result socket stays. |
| `src/myteam/tasks/terminal/control_channel.py` | Keep | **Important:** keep the recursive child-session control protocol. This is part of the required session suspend/resume behavior. |
| `src/myteam/tasks/terminal/session.py` | Keep / minor rewrite | Orchestrates PTY + result channel + control channel. This should remain the core transport assembly. |
| `src/myteam/tasks/terminal/session_registry.py` | Keep | Needed for env-var/socket discovery and recursive communication. |

### Runtime logic currently under `tasks/`

| File | Action | Notes |
|---|---|---|
| `src/myteam/tasks/__init__.py` | Rewrite | Replace task-runtime exports with the streamlined workflow/session runtime exports. |
| `src/myteam/tasks/README.md` | Delete | Legacy task subsystem documentation. |
| `src/myteam/tasks/definition/__init__.py` | Delete or rewrite | If the task schema layer disappears, this package should go with it. |
| `src/myteam/tasks/definition/models.py` | Rewrite | Replace task-step models with the new session/workflow result models. Remove YAML-step schema machinery. |
| `src/myteam/tasks/definition/parser.py` | Delete or rewrite | YAML task loading is going away. Keep only if you need a tiny workflow frontmatter loader. |
| `src/myteam/tasks/definition/default_task.py` | Delete if unused | Legacy default-task fallback should not survive unless the simplified workflow model still needs it. |
| `src/myteam/tasks/execution/__init__.py` | Rewrite | Collapse toward the public `run_agent` entrypoint. |
| `src/myteam/tasks/execution/steps.py` | Rewrite | This should become the core `run_agent` implementation or be moved into the new workflow runtime module. |
| `src/myteam/tasks/execution/engine.py` | Delete | Multi-step orchestration is part of the old YAML task system. |
| `src/myteam/tasks/execution/runner.py` | Delete | Child-task execution is legacy once `run_agent` is the center. |
| `src/myteam/tasks/execution/cli_commands.py` | Delete | Legacy task CLI control channel commands should go. |
| `src/myteam/tasks/execution/prompts.py` | Rewrite | Keep only if prompt assembly is still shared by `run_agent` and recursive session resumption. Remove task-specific wording. |
| `src/myteam/tasks/execution/usage.py` | Rewrite | Preserve usage aggregation/reporting, but detach it from task terminology. |
| `src/myteam/tasks/execution/errors.py` | Rewrite | Simplify error types around the new runtime model. |
| `src/myteam/tasks/resolution/__init__.py` | Rewrite or delete | Keep only the session-resolution pieces that are still needed. |
| `src/myteam/tasks/resolution/reference_resolver.py` | Delete | `$step.path` references are task-engine behavior. |
| `src/myteam/tasks/resolution/session_resolution.py` | Keep / minor rewrite | Session-id discovery is required for resume/fork and recursive sessions. |

### Templates

| File | Action | Notes |
|---|---|---|
| `src/myteam/templates/new_skill.md` | Keep | Skill template stays. |
| `src/myteam/templates/new_skill.py` | Keep | Skill template stays. |
| `src/myteam/templates/folder_description.md` | Keep / minor rewrite | Keep if hierarchical resource folders remain. |
| `src/myteam/templates/skill_load_template.py` | Keep / minor rewrite | Should still reflect the final skill-load contract. |
| `src/myteam/templates/builtin_*` skill templates | Keep | These are unrelated to workflow rewrite. |
| `src/myteam/templates/new_workflow.md` | Rewrite | Remove task-era wording; make it a simple workflow prompt template. |
| `src/myteam/templates/new_workflow.py` | Create / rewrite | Ensure the Python workflow template matches the new public API. |
| `src/myteam/templates/workflow_markdown_wrapper.py` | Rewrite | Must render Markdown workflow prompts and call `run_agent`; no YAML task engine behavior. |
| `src/myteam/templates/task_definition_template.py` | Delete | Legacy task template. |
| `src/myteam/templates/task_definition_template.yaml` | Delete | Legacy YAML task template. |
| `src/myteam/templates/agents_md_template.md` | Delete or rewrite | Keep only if it is still used for a new resource model. Otherwise it is legacy role/task material. |
| `src/myteam/templates/role_definition_template.md` | Delete | Legacy role system material. |
| `src/myteam/templates/role_load_template.py` | Delete | Legacy role system material. |
| `src/myteam/templates/root_role_load_template.py` | Delete | Legacy role system material. |
| `src/myteam/templates/explain_resources.md` | Rewrite | Must explain the current skills/workflows model. |
| `src/myteam/templates/builtin_changelog_skill_definition.md` | Keep | Not workflow-specific. |
| `src/myteam/templates/builtin_changelog_skill_load_template.py` | Keep | Not workflow-specific. |
| `src/myteam/templates/builtin_migrate_skill_definition.md` | Keep | Not workflow-specific. |
| `src/myteam/templates/builtin_migrate_skill_load_template.py` | Keep | Not workflow-specific. |
| `src/myteam/templates/builtin_myteam_skill_definition.md` | Keep | Not workflow-specific. |

### Migrations / version notes

| File | Action | Notes |
|---|---|---|
| `src/myteam/migrations/*` | Keep unless proven obsolete | These are version-history docs, not workflow runtime. Leave them alone unless the rewrite needs a packaging cleanup. |

---

## Implementation Order

1. Preserve and stabilize the session transport layer first.
   - keep PTY, result channel, control channel, and session registry behavior intact
   - confirm recursive child-session suspension/resume still works

2. Implement and stabilize `run_agent` as the core callable.
   - this is the remaining primary focus
   - keep usage reporting and session discovery
   - preserve recursive session suspend/resume behavior
   - remove the task-engine shape from the API

3. Remove YAML task orchestration.
   - delete multi-step engine code
   - delete step reference resolution
   - delete child-task request handling that is not part of the session recursion protocol

4. Rewrite workflow docs/templates.
   - workflows should be “prompt + run_agent”
   - Markdown workflows should be a thin wrapper around prompt rendering

5. Clean up naming where needed.
   - any remaining `task` terminology in public docs, CLI names, or module names should be replaced with workflow/session language unless it refers to the preserved control protocol itself
   - do not spend effort on resource listing/discovery unless a specific compatibility issue shows up

---

## Non-Negotiables

- Do **not** remove the session nonce plumbing.
- Do **not** remove the socket-based result reporting.
- Do **not** remove the ability for child sessions to suspend the parent and then resume it.
- Do **not** remove the agent adapter abstraction.
- Do **not** remove the skills/list/explain resource model.

If a change threatens any of the above, it is out of scope for this rewrite.
