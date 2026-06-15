# Uses Selected Local Root

## Purpose

Honor caller-selected local roots.

---

# Context

Commands that operate on the project-local tree use one selected local root for
that invocation. The default local root is `.myteam/`. Packaged built-in skills
live outside the project-local tree under the reserved `builtins/` namespace.

---

# Action

The caller passes `--prefix <path>` to a command that supports local root
selection.

---

# Interaction

| Action | Outcome |
| --- | --- |
| `myteam init --prefix <path>` | Initializes the root role in the selected local root instead of `.myteam/`. |
| `myteam new role <name> --prefix <path>` | Creates the role under the selected local root. |
| `myteam new skill <name> --prefix <path>` | Creates the skill under the selected local root. |
| `myteam get role ... --prefix <path>` | Resolves non-built-in roles from the selected local root. |
| `myteam get skill <name> --prefix <path>` | Resolves non-built-in skills from the selected local root. |
| `myteam get skill builtins/... --prefix <path>` | Resolves the built-in skill from the packaged built-in tree while preserving the selected local root as project context for the loader. |
| `myteam remove <name> --prefix <path>` | Removes the target node from the selected local root. |
| `myteam download <roster> --prefix <path>` | Uses the selected local root as the default managed-install destination when no explicit destination is provided. |
| `myteam update [path] --prefix <path>` | Searches for or resolves managed installs under the selected local root. |
| `myteam start <workflow> --prefix <path>` | Resolves the workflow file from the selected local root. |

---

# Outcome

`--prefix` changes only the project-local root used by that command invocation.
It does not change where packaged built-in skills are stored or resolved from.

When a command accepts both `--prefix` and a more specific path-like input, the
specific path-like input still determines the final target documented by that
command.

---

# Related Scenarios

- [../instruction_loading/loads_instruction_nodes.md](../instruction_loading/loads_instruction_nodes.md)
- [../workflows/runs_workflows.md](../workflows/runs_workflows.md)
- [../rosters/manages_rosters.md](../rosters/manages_rosters.md)
