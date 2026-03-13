# Change Log

## 0.2.3

- Switched YAML frontmatter parsing in `list_roles` / `list_skills` to `PyYAML` instead of manual line parsing.
- This fixes frontmatter metadata handling for valid YAML that was previously misparsed or skipped.

## 0.2.1

- `list_roles` / `list_skills` now prefer `name` + `description` from YAML frontmatter in `role.md` / `skill.md`.
  - If frontmatter metadata is missing, listing falls back to `info.md`; if `info.md` is absent, description is empty.
  - Skill/role list headers continue to use folder names as display names.
- `new role` and `new skill` no longer create `info.md`.
- Removed unused `role_info_template.md` and `skill_info_template.md` templates.
- Added support for uppercase `ROLE.md` / `SKILL.md` in role/skill detection, listing metadata, and `get` output.

## 0.2.0

Refactored design to support nested roles and skills.

- Skill folders are identified by `skill.md` and role folders by `role.md`
- Better presentation of tools in skills and roles
