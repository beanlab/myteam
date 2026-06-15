# Manages Local Tree

## Purpose

Create and remove local agent-system nodes.

---

# Context

`myteam` is run from a project root. The command uses the selected local root,
which defaults to `.myteam/` unless the invocation selects another root.

Role and skill paths are slash-delimited and describe directories below the
selected local root.

---

# Action

The caller runs a command that initializes the local tree, scaffolds a role or
skill, or removes an existing local node.

---

# Interaction

| Action | Outcome |
| --- | --- |
| `myteam init` | Creates the selected local root as the root role directory when needed, creates `role.md`, `load.py`, and the tracked-version metadata file in that root, creates `AGENTS.md` when absent, and leaves an existing `AGENTS.md` in place. |
| `myteam new role <path>` | Creates the target directory under the selected local root with a `role.md` definition file and a `load.py` loader. |
| `myteam new skill <path>` | Creates the target directory under the selected local root with a `skill.md` definition file and a `load.py` loader. |
| `myteam remove <path>` | Deletes the target role or skill directory and all of its contents from the selected local root. |

---

# Outcome

After initialization succeeds, the current directory is ready for
`myteam get role`, and packaged maintenance skills under the reserved
`builtins/` namespace are available without being copied into the project tree.

After role or skill scaffolding succeeds, the new node is loadable with
`myteam get role <path>` or `myteam get skill <path>`.

After removal succeeds, the removed node is no longer available to load.

The command exits with an error and reports the failure on standard error when
the target already exists during scaffolding, does not exist during removal, is
not a directory during removal, or cannot be removed.

---

# Related Scenarios

- [uses_selected_local_root.md](uses_selected_local_root.md)
- [../instruction_loading/loads_instruction_nodes.md](../instruction_loading/loads_instruction_nodes.md)
