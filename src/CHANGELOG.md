# Change Log

## 0.2.11

- *Note: the workflows feature is experimental and may change in the future*
- Added `myteam start <workflow>` to load and execute YAML workflow definitions

## 0.2.10

- Default generated role and skill loaders now present skills first, tools second, and roles last.
- Added packaged changelog data inside the `myteam` package so `builtins/changelog` works from installed releases instead of relying on repository-only files.
- Added migration guidance for updating existing `.myteam` loaders to the new discovery order.

## 0.2.9

- Added `--prefix <path>` support to the local-tree commands so `init`, `new`, `get`, and `remove`
  can operate against a project-local root other than `.myteam/`.
- Extended `myteam download` and `myteam update` so their default managed-install root also honors
  `--prefix <path>`.
- Refactored project-local root resolution into shared helpers so custom prefixes work consistently
  across command execution, generated loaders, and managed roster updates.

## 0.2.8

- Added `myteam update [path]` for refreshing managed roster installs from recorded source
  metadata.
- `myteam update` now supports updating a single managed subtree or scanning `.myteam/` for all
  managed installs.
- Refactored roster installation so `download` and `update` share the same managed-install path.

## 0.2.7

- `myteam download` now installs only folder rosters as managed local folders instead of flattening
  roster contents directly into the destination root.
- Default downloads preserve the remote roster path under `.myteam/`, and explicit destinations are
  treated as managed install roots under `.myteam/`.
- Managed roster installs now write `.source.yml` at the folder root so future commands can track
  their origin.
- `myteam download` now fails when the target already exists, directing same-source reinstalls toward
  `myteam update <path>` and rejecting unrelated existing content.
- Removed support for single-file roster downloads.

## 0.2.6

- `myteam init` now stores the creating `myteam` version in `.myteam/.myteam-version`.
- Built-in maintenance skills now live inside the package under the reserved `builtins/` namespace
  instead of being scaffolded into project `.myteam/` trees.
- The default root role loader now alerts the agent when the installed `myteam` version is newer than the tracked `.myteam` version.
- Added packaged migration notes for upgrading older `.myteam` trees to the new tracked-version and built-in maintenance-skill flow.
- Upgrade guidance is now agent-mediated through the root-role notice plus the built-in `builtins/migration` and `builtins/changelog` skills, rather than a dedicated migration command.

## 0.2.5

- Refactored the CLI module so `src/myteam/cli.py` now only contains command wiring and `main()`.
- Moved CLI command implementations into dedicated modules to separate command logic from path/config helpers.
- Consolidated package versioning to a single source of truth in `pyproject.toml` while preserving `myteam --version`.
- Added `scratch/` to `.gitignore` for local workspace artifacts.
- Added a GitHub Actions workflow that runs after pull requests are merged into `main`, builds the merged commit, and posts the released version plus matching changelog notes to Discord.
- The Discord notification workflow is configured to use a repository secret for the webhook URL instead of hardcoding the credential in the repository.
- Changed both GitHub Actions workflows so they trigger on pushes to `main`.
- Updated the Discord notification workflow to report the pushed commit instead of pull request merge metadata.
- Updated the PyPI publish and Discord notification workflows so they only run for pushes to `main` when `pyproject.toml`'s version changed and that version is not already present on PyPI.

## 0.2.4

- Rewrote the README to match the current agent-centered workflow and nested role/skill model.
- Updated command documentation and examples to reflect the current `myteam get role`, `myteam get skill`, `myteam list`, and `myteam download` interfaces.
- Clarified how root roles, nested paths, frontmatter metadata, and roster downloads work in practice.

## 0.2.3

- Switched YAML frontmatter parsing in `list_roles` / `list_skills` to `PyYAML` instead of manual line parsing.
- This fixes frontmatter metadata handling for valid YAML that was previously misparsed or skipped.

## 0.2.2

- Renamed the roster commands to `myteam list` and `myteam download` to align the CLI with the broader role/skill command structure.
- Extended roster downloads so they can target a custom destination instead of always writing into `.myteam/`.
- Added support for downloading single-file rosters by fetching the repository tree recursively and handling blob entries directly.
- Updated the skill template to include YAML frontmatter fields for `name` and `description`.

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
