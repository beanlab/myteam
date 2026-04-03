# Application Interface

## Purpose

`myteam` is a command-line application for building file-based agent systems.

Its public purpose is to let a project define agent instructions in a local `.myteam/` directory and
then let agents load those instructions themselves. The tool treats roles, skills, and tools as
discoverable filesystem objects that can be created, listed, loaded, downloaded, and removed through
the CLI. It also ships version-aware built-in maintenance skills so agents can surface upgrade
guidance for older `.myteam/` trees without copying those built-ins into each project.

The intended workflow is:

1. A project initializes `.myteam/`.
2. A human author creates or downloads roles and skills.
3. Agents run `myteam get role ...` and `myteam get skill ...` to load the instructions relevant to their current task.
4. Each loaded role or skill reveals the next level of roles, skills, and tools that are available from that point in the hierarchy.

## Operating Model

`myteam` operates relative to the current working directory.

- The application treats the current directory as the project root.
- The root agent system lives in `.myteam/`.
- Roles and skills are organized as nested directories under `.myteam/`.
- A loadable role directory contains `role.md` or `ROLE.md` and a `load.py`.
- A loadable skill directory contains `skill.md` or `SKILL.md` and a `load.py`.
- Packaged built-in skills also exist under the reserved `builtins/` namespace and are loadable even
  though they do not live in the project's `.myteam/` directory.
- Instruction files may contain YAML frontmatter. When a role or skill is loaded, the frontmatter is not shown in the printed instructions.

## Interface Guarantees

At the black-box level, `myteam` provides these categories of behavior:

- It can scaffold a new `.myteam/` tree.
- It can scaffold new role and skill nodes inside that tree.
- It can record which `myteam` version last initialized or refreshed a `.myteam/` tree.
- It can load and print instructions for a role or skill.
- It can resolve skills from either the project `.myteam/` tree or the packaged built-in tree,
  depending on the requested namespace.
- It can alert the caller when the installed `myteam` version is newer than the tracked `.myteam` version.
- It can expose packaged migration and changelog guidance through built-in maintenance skills.
- It can remove a previously created node.
- It can list downloadable rosters from a remote repository.
- It can download a roster into a local destination.
- It can update a previously downloaded managed roster install from its recorded source metadata.
- It can report its version string.

Successful commands either:

- create or remove files and directories in or under the current working directory,
- print instructions or listings to standard output,
- download roster files into a destination directory,
- or return a version string.

When a command cannot complete, it exits with an error and reports the failure on standard error.

## Command Reference

### `myteam init`

Initializes a new agent system in the current working directory.

Expected outcome on success:

- Creates `.myteam/` as the root role directory if it does not already exist.
- Creates `.myteam/role.md`.
- Creates `.myteam/load.py`.
- Creates a `.myteam` metadata file that stores the current `myteam` version.
- Creates `AGENTS.md` if `AGENTS.md` does not already exist.
- Leaves an existing `AGENTS.md` in place.

User-visible result:

- After success, the current directory is ready for `myteam get role`.
- The generated root role can later detect when the installed `myteam` release is newer than the stored `.myteam` version.
- Packaged maintenance skills under the reserved `builtins/` namespace are available for later use
  without being copied into the project tree.

### `myteam new role <path>`

Creates a new role below `.myteam/`.

Inputs:

- `<path>` is slash-delimited and may describe a nested role such as `engineer/frontend`.

Expected outcome on success:

- Creates the target directory under `.myteam/`.
- Creates a `role.md` definition file in that directory.
- Creates a `load.py` loader in that directory.

User-visible result:

- The new role becomes loadable with `myteam get role <path>`.

Failure conditions that matter at the interface:

- If the target directory already exists, the command exits with an error and does not overwrite it.

### `myteam new skill <path>`

Creates a new skill below `.myteam/`.

Inputs:

- `<path>` is slash-delimited and may describe a nested skill such as `python/testing`.

Expected outcome on success:

- Creates the target directory under `.myteam/`.
- Creates a `skill.md` definition file in that directory.
- Creates a `load.py` loader in that directory.

User-visible result:

- The new skill becomes loadable with `myteam get skill <path>`.

Failure conditions that matter at the interface:

- If the target directory already exists, the command exits with an error and does not overwrite it.

### `myteam get role [path]`

Loads and prints a role's instructions.

Inputs:

- With no `path`, the command loads the root role at `.myteam/`.
- With a `path`, it loads the nested role under `.myteam/<path>`.

Expected outcome on success:

- Executes the target role's `load.py`.
- Prints the role instructions.
- Prints built-in guidance about roles, skills, and tools when the loader includes it.
- Prints the immediately discoverable child roles, child skills, and Python tools exposed from that node.

User-visible result:

- The caller receives the instructions and local discovery context for that role.
- When loading the root role generated by `myteam init`, the caller also receives an upgrade notice if the installed `myteam` release is newer than the tracked `.myteam` version.
- If the tracked `.myteam` version file is missing, the generated root role treats the tree as an untracked legacy `.myteam` tree and may still print upgrade guidance instead of failing.
- The generated root role can tell the caller that it may assist with migrating the existing
  `.myteam/` tree and that, if the user agrees, the agent should load
  `myteam get skill builtins/migration` to perform the migration correctly.

Failure conditions that matter at the interface:

- If the target path is not a valid role directory, the command exits with an error.
- If the target role exists but lacks `load.py`, the command exits with an error.
- If the loader itself exits non-zero, `myteam` exits with the same non-zero status.

### `myteam get skill <path>`

Loads and prints a skill's instructions.

Inputs:

- `<path>` is a slash-delimited skill path.

Expected outcome on success:

- Resolves `builtins/...` from the packaged built-in skill tree.
- Resolves all other skill paths from `.myteam/`.
- Executes the resolved skill's loader.
- Prints the skill instructions.
- Prints any child roles, child skills, and Python tools exposed from that node by the loader.

User-visible result:

- The caller receives the instructions and local discovery context for that skill.
- Built-in maintenance skills may additionally print migration guidance or release notes derived from the installed `myteam` package.
- If the tracked `.myteam` version file is missing, built-in maintenance skills treat the tree as an untracked legacy `.myteam` tree and still print the relevant upgrade guidance.

Failure conditions that matter at the interface:

- If the target path is not a valid skill in the selected source tree, the command exits with an error.
- If the resolved skill exists but lacks the required loader entry point, the command exits with an error.
- If the loader itself exits non-zero, `myteam` exits with the same non-zero status.

### `myteam remove <path>`

Removes a role or skill directory from `.myteam/`.

Inputs:

- `<path>` is a slash-delimited path under `.myteam/`.

Expected outcome on success:

- Deletes the target directory and all of its contents recursively.

User-visible result:

- The removed node is no longer available to load.

Failure conditions that matter at the interface:

- If the target path does not exist, the command exits with an error.
- If the target path exists but is not a directory, the command exits with an error.
- If the directory cannot be removed, the command exits with an error.

### `myteam list`

Lists roster entries available from the default remote roster repository.

Expected outcome on success:

- Connects to the configured roster repository.
- Prints one available roster entry path per line.

User-visible result:

- The caller can inspect the output and choose a roster name for `myteam download`.

Failure conditions that matter at the interface:

- If the repository path is invalid or the remote request fails, the command exits with an error.

### `myteam download <roster>`

Downloads a named roster folder from a remote repository as a managed local install.

Inputs:

- `<roster>` identifies the remote roster folder to download.
- The command also supports an optional destination and alternate repository through its CLI wiring.
- If no destination is provided, the roster path is installed under `.myteam/` using the same relative
  folder path as the remote roster.

Expected outcome on success:

- Downloads the requested roster folder content from the configured repository.
- Creates one managed local folder for that install.
- Writes a `.source.yml` provenance file at the root of the managed local folder.
- Writes downloaded files inside that managed local folder while preserving their relative paths within
  the roster.
- Prints progress while downloading.

User-visible result:

- The downloaded roster becomes available on disk as a managed folder, ready to be loaded or edited.
- The managed folder records enough source information for later provenance-aware commands.

Failure conditions that matter at the interface:

- If the roster name does not exist in the repository, the command exits with an error and reports available roster names.
- If the requested roster resolves to a single file instead of a folder, the command exits with an error.
- If the destination already contains the same managed source, the command exits with an error that
  tells the caller to run `myteam update <path>` instead of using `download` again.
- If unrelated content already exists at the destination path, the command exits with an error that
  explains the content is not the same managed source and tells the caller to delete it or choose a
  different destination instead of merging.
- If the remote metadata or file downloads fail, the command exits with an error.

### `myteam --version`

Reports the application version.

Expected outcome on success:

- Returns a version string in the form `myteam <version>`.

User-visible result:

- The caller can verify which installed version of `myteam` is running.

### `myteam update [path]`

Refreshes one or more managed downloaded folders from their recorded source metadata.

Inputs:

- With a `path`, the command updates the managed folder rooted at `.myteam/<path>` or at the provided
  path if the caller passes an explicit `.myteam/...` path.
- With no path, the command scans `.myteam/` recursively for managed download roots and updates each
  one independently.

Expected outcome on success:

- Reads `.source.yml` from each targeted managed folder.
- Re-downloads the folder content from the recorded repository, roster path, and ref.
- Existing content at the managed target is deleted before re-download.
- After deletion, the command performs the same managed install behavior as `myteam download` using the
  recorded source metadata.

User-visible result:

- Managed downloaded content can be refreshed without re-specifying its remote source.
- A project with multiple managed downloaded folders can refresh all of them in one command.

Failure conditions that matter at the interface:

- If the requested path does not identify a managed downloaded folder with `.source.yml`, the command
  exits with an error.
- If `myteam update` is run with no path and no managed downloaded folders are found, the command exits
  with an error.
- If a targeted managed folder has invalid or incomplete source metadata, the command exits with an
  error.
- If the recorded remote roster no longer exists, resolves to a file, or cannot be fetched, the command
  exits with an error.

## Observable Conventions

The following behavior is part of the current application contract:

- Paths are interpreted relative to the current working directory.
- Nested role and skill names use slash-delimited paths.
- Instruction loading is driven by executable `load.py` files stored alongside role and skill definitions.
- The `builtins/` skill namespace is reserved for packaged built-in skills shipped with the installed
  `myteam` version.
- `builtins/...` paths resolve only from the packaged built-in tree.
- All other skill paths resolve only from project `.myteam/`.
- Role and skill metadata may be surfaced from YAML frontmatter in definition files.
- A `.myteam/` tree may carry a stored `myteam` version used for upgrade notices and migration guidance.
- Upgrade guidance is surfaced through the generated root role and built-in maintenance skills, not through a dedicated migration CLI command.
- If the tracked version file is missing, upgrade-related built-in loaders treat the tree as a legacy untracked `.myteam` tree rather than failing.
- Managed downloaded folders are identified by a `.source.yml` file at the root of the managed install.
- Errors are communicated as command failure plus an error message on standard error.

## Out of Scope

This interface document does not define:

- internal module boundaries,
- template implementation details,
- the specific prose content of any project's role or skill instructions,
- or the contents of any external roster repository.
