# Loads Instruction Nodes

## Purpose

Load roles and skills.

---

# Context

Role directories contain `role.md` or `ROLE.md` and a `load.py`. Skill
directories contain `skill.md` or `SKILL.md` and a `load.py`. Instruction files
may contain YAML frontmatter; frontmatter is not shown in loaded instructions.

Non-built-in role and skill paths resolve from the selected local root.
Packaged built-in skills resolve from the reserved `builtins/` namespace.

---

# Action

The caller asks `myteam` to load a role or skill.

---

# Interaction

| Action | Outcome |
| --- | --- |
| `myteam get role` | Loads the root role at the selected local root. |
| `myteam get role <path>` | Loads the nested role under the selected local root. |
| `myteam get skill <path>` | Resolves and loads the skill from the selected local root. |
| `myteam get skill builtins/...` | Resolves and loads the skill from the packaged built-in tree. |

---

# Outcome

The command executes the resolved node's `load.py`, prints the node
instructions, and prints immediately discoverable child roles, child skills,
and Python tools exposed by that loader.

When the loader includes built-in explanation text for roles, skills, and
tools, the command prints that guidance as part of the loaded role or skill
output.

The command exits with an error when the target path is not a valid role or
skill directory, when the resolved node lacks the required loader entry point,
or when the loader exits non-zero. Loader exit status propagates as command
failure.

---

# Related Scenarios

- [surfaces_upgrade_guidance.md](surfaces_upgrade_guidance.md)
- [../local_tree/manages_local_tree.md](../local_tree/manages_local_tree.md)
- [../local_tree/uses_selected_local_root.md](../local_tree/uses_selected_local_root.md)
