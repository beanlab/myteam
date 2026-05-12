# Surfaces Upgrade Guidance

## Purpose

Expose version-aware maintenance help.

---

# Context

A local tree may contain tracked-version metadata recording the `myteam`
version that initialized or refreshed that tree. The installed `myteam` package
also ships built-in maintenance skills under the reserved `builtins/`
namespace.

---

# Action

The caller loads the generated root role or a packaged built-in maintenance
skill.

---

# Interaction

| Action | Outcome |
| --- | --- |
| `myteam get role` with an older tracked local tree | The generated root role can alert the caller that the installed `myteam` release is newer than the stored tracked version. |
| `myteam get role` with missing tracked-version metadata | The generated root role treats the selected local tree as an untracked legacy tree and may still print upgrade guidance instead of failing. |
| Root-role migration notice | The generated root role can tell the caller that it may assist with migration and should load `myteam get skill builtins/migration` if the user agrees. |
| `myteam get skill builtins/migration` | Prints packaged migration guidance for the selected local tree context. |
| `myteam get skill builtins/changelog` | Prints release notes derived from the installed `myteam` package. |

---

# Outcome

Upgrade guidance is surfaced through the generated root role and built-in
maintenance skills, not through a dedicated migration CLI command.

Built-in maintenance skills are available without being copied into the
project-local tree. If tracked-version metadata is missing, upgrade-related
built-in loaders treat the tree as a legacy untracked local tree rather than
failing solely because the version file is absent.

---

# Related Scenarios

- [loads_instruction_nodes.md](loads_instruction_nodes.md)
- [../local_tree/manages_local_tree.md](../local_tree/manages_local_tree.md)
