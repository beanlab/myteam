# Custom Local Prefix Feature Plan

## Framework Refactor

### Current design

The local-tree commands currently assume one hard-coded root directory:

- `src/myteam/paths.py` defines `AGENTS_DIRNAME = ".myteam"`
- `agents_root(base)` always returns `<cwd>/.myteam`
- `init`, `new role`, `new skill`, `get role`, `get skill`, and `remove` all rely on that helper
- tests and user-facing docs reflect the same fixed-path assumption

That design kept the initial CLI simple, but it couples command behavior to one project-local folder
name and makes selective customization impossible.

### Refactor goal

Refactor local-tree path resolution so commands can operate against a caller-selected root directory
without changing their higher-level behavior.

The refactor should separate:

- choosing the local tree root for one command invocation
- defaulting that root to `.myteam`
- resolving role and skill paths under that chosen root
- resolving packaged built-in skills independently of the local root

### Planned refactor

1. Introduce one shared local-root resolver in `src/myteam/paths.py`.
   - Keep `.myteam` as the default root name.
   - Accept an optional CLI-provided prefix string.
   - Resolve the selected local root relative to the current working directory.
2. Update command functions in `src/myteam/commands.py` to accept an optional `prefix` argument.
   - `init`
   - `new_role`
   - `new_skill`
   - `get_role`
   - `get_skill`
   - `remove`
3. Keep built-in skill resolution separate from the project-local root.
   - `builtins/...` should continue resolving from the packaged built-in tree.
   - When built-in skills need the project root context, pass the selected local root rather than the default `.myteam`.
4. Extend the managed-roster commands to share the same default-root selection model.
   - `download` should use the selected prefix when computing its default managed install root.
   - `update` should use the selected prefix when scanning for managed installs and when resolving a
     relative managed install path.
   - Explicit download destinations should remain stronger than the default selected prefix.
5. Update CLI wiring so Fire exposes `--prefix` on the supported commands without introducing a second configuration mechanism.

### Why this framework change is sufficient

Once local-root selection is explicit, the feature logic is small:

- parse an optional `--prefix`
- compute the selected local root once
- run the existing command behavior against that root

That keeps the business behavior stable and avoids scattering ad hoc path handling through each
command implementation.

## Feature Addition

### Behavior to implement

Implement CLI-selectable local roots for the local-tree commands with the following behavior:

1. `myteam init`
   - continues creating `.myteam/` by default
   - supports `myteam init --prefix .agents`
   - creates the root role, loader, and tracked-version file inside the selected prefix directory
2. `myteam new role <path>`
   - continues creating roles under `.myteam/` by default
   - supports `myteam new role <path> --prefix .agents`
   - creates the role below the selected local root
3. `myteam new skill <path>`
   - continues creating skills under `.myteam/` by default
   - supports `myteam new skill <path> --prefix .agents`
   - keeps the reserved `builtins/` namespace restriction unchanged
4. `myteam get role [path]`
   - continues loading roles from `.myteam/` by default
   - supports `myteam get role [path] --prefix .agents`
   - uses the selected local root both for role lookup and for root-loader tracked-version behavior
5. `myteam get skill <path>`
   - continues resolving non-built-in skills from `.myteam/` by default
   - supports `myteam get skill <path> --prefix .agents`
   - continues resolving `builtins/...` from packaged built-ins while passing the selected local root as project context
6. `myteam remove <path>`
   - continues removing directories from `.myteam/` by default
   - supports `myteam remove <path> --prefix .agents`
   - removes only paths under the selected local root

### Non-goals for this feature

- adding an environment-variable-based prefix override
- changing the default local root away from `.myteam`

### Test updates anticipated by this plan

The test suite should be extended with high-level command tests that verify:

- `init --prefix <path>` creates the expected root files under the custom prefix
- `new role` and `new skill` honor `--prefix`
- `get role` and `get skill` honor `--prefix`
- built-in skills still load when `--prefix` is present
- `remove --prefix` removes the targeted directory under the custom root
- `download --prefix` changes the default managed install root when no explicit destination is provided
- `update --prefix` scans or resolves managed installs under the selected custom root
- omitting `--prefix` preserves the current `.myteam` behavior
