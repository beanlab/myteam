# Change Log

## 0.2.1

- `list_roles` / `list_skills` now prefer `name` + `description` from YAML frontmatter in `role.md` / `skill.md`.
  - If frontmatter metadata is missing, listing falls back to `info.md`; if `info.md` is absent, description is empty.
  - Skill/role list headers continue to use folder names as display names.
- `new role` and `new skill` no longer create `info.md`.
  - Removed unused `role_info_template.md` and `skill_info_template.md` templates.

## 0.2.0

Refactored design to support nested roles and skills.

- Skill folders are identified by `skill.md` and role folders by `role.md`
- Better presentation of tools in skills and roles
