# list_skills controls built-in skill visibility

## Purpose

Control packaged skill discovery.

---

# Context

A loader or other integration is listing skills for a selected project-local tree by calling
`list_skills`. The selected tree may contain project-defined skills, and the installed `myteam`
package may also provide skills under the reserved `builtins/` namespace.

---

# Action

The caller requests a skill listing and chooses whether packaged built-in skills should be included.

---

# Interaction

| Action | Outcome |
| --- | --- |
| Omit the built-in visibility option | The listing preserves existing compatibility behavior by including the packaged `builtins` entry when it is available at the project root. |
| Set the option to include built-ins | The listing includes the packaged `builtins` entry when it is available at the project root. |
| Set the option to hide built-ins | The listing omits packaged built-in entries while still listing project-defined skills from the selected local tree. |

---

# Outcome

Skill discovery callers can make built-in visibility explicit without duplicating namespace-specific
filtering outside `list_skills`.

The reserved `builtins/` namespace remains unavailable for project-defined skills regardless of the
listing option.

The option controls skill listings only; role listings do not gain matching built-in visibility
behavior from this scenario.
