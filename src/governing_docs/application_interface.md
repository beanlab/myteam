# Application Interface

## Purpose

`myteam` is a command-line application for building file-based agent systems.

Its public purpose is to let a project define agent instructions in a local `.myteam/` directory and
then let agents load those instructions themselves. The tool treats roles, skills, and tools as
discoverable filesystem objects that can be created, listed, loaded, downloaded, and removed through
the CLI.

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
- Instruction files may contain YAML frontmatter. When a role or skill is loaded, the frontmatter is not shown in the printed instructions.

## Interface Guarantees

At the black-box level, `myteam` provides these categories of behavior:

- It can scaffold a new `.myteam/` tree.
- It can scaffold new role and skill nodes inside that tree.
- It can load and print instructions for a role or skill.
- It can remove a previously created node.
- It can list downloadable rosters from a remote repository.
- It can download a roster into a local destination.
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
- Creates `AGENTS.md` if `AGENTS.md` does not already exist.
- Leaves an existing `AGENTS.md` in place.

User-visible result:

- After success, the current directory is ready for `myteam get role`.

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

Failure conditions that matter at the interface:

- If the target path is not a valid role directory, the command exits with an error.
- If the target role exists but lacks `load.py`, the command exits with an error.
- If the loader itself exits non-zero, `myteam` exits with the same non-zero status.

### `myteam get skill <path>`

Loads and prints a skill's instructions.

Inputs:

- `<path>` is a slash-delimited skill path under `.myteam/`.

Expected outcome on success:

- Executes the target skill's `load.py`.
- Prints the skill instructions.
- Prints any child roles, child skills, and Python tools exposed from that node by the loader.

User-visible result:

- The caller receives the instructions and local discovery context for that skill.

Failure conditions that matter at the interface:

- If the target path is not a valid skill directory, the command exits with an error.
- If the target skill exists but lacks `load.py`, the command exits with an error.
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

Downloads a named roster from a remote repository.

Inputs:

- `<roster>` identifies the roster entry to download.
- The command also supports an optional destination and alternate repository through its CLI wiring.

Expected outcome on success:

- Downloads the requested roster content from the configured repository.
- Writes the downloaded files into `.myteam/` by default.
- Creates destination directories as needed.
- Prints progress while downloading.

User-visible result:

- The downloaded roster becomes available on disk in the destination directory, ready to be loaded or edited.

Failure conditions that matter at the interface:

- If the roster name does not exist in the repository, the command exits with an error and reports available roster names.
- If the remote metadata or file downloads fail, the command exits with an error.

### `myteam --version`

Reports the application version.

Expected outcome on success:

- Returns a version string in the form `myteam <version>`.

User-visible result:

- The caller can verify which installed version of `myteam` is running.

## Observable Conventions

The following behavior is part of the current application contract:

- Paths are interpreted relative to the current working directory.
- Nested role and skill names use slash-delimited paths.
- Instruction loading is driven by executable `load.py` files stored alongside role and skill definitions.
- Role and skill metadata may be surfaced from YAML frontmatter in definition files.
- Errors are communicated as command failure plus an error message on standard error.

## Out of Scope

This interface document does not define:

- internal module boundaries,
- template implementation details,
- the specific prose content of any project's role or skill instructions,
- or the contents of any external roster repository.
