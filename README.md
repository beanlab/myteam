# Myteam

Simple CLI for managing an on-disk roster of agent roles. Myteam creates a lightweight structure (`AGENTS.md` plus
a `.myteam/` directory) that other tools can read to understand available roles and their instructions.

## Features

- Zero-dependency CLI (Python 3.11+)
- Commands to create, remove, and inspect roles
- Works from any directory (operates relative to the current working directory)

## Requirements

- Python 3.11 or newer

## Installation

```bash
pip install myteam
```

## Quick start

1) `myteam init` — set up `AGENTS.md` and `.myteam/` with a top-level `role.md` and `load.py`.
2) `myteam new role developer` — add another role (optional).
3) Edit `.myteam/role.md` for the top-level instructions, and `.myteam/<role>/info.md` / `.myteam/<role>/role.md` for
   specific roles.
4) `myteam get role [role]` — run the role’s `load.py` (or print `role.md`), and when omitted it runs the top-level
   `.myteam/load.py`.

## Commands

| Command                    | Purpose                                                                                                     |
|---------------------------|-------------------------------------------------------------------------------------------------------------|
| `myteam init`             | Initialize `AGENTS.md` and `.myteam/` with top-level `role.md` and `load.py`.                               |
| `myteam new role <role>`  | Create a new role directory with `load.py`, empty `info.md`, and `role.md`.                                 |
| `myteam remove <role>`    | Delete the specified role directory and its contents.                                                       |
| `myteam get role [role]`  | Run a role’s `load.py` (or print `role.md`); when omitted, runs the top-level `.myteam/load.py`.            |

## What gets created

Running `myteam init` produces:

```
AGENTS.md               # Onboarding note for agents
.myteam/
  ├── role.md            # Top-level role instructions
  ├── load.py            # Prints top-level instructions plus other role info.md files
  └── <new-role>/        # Created by `myteam new role <role>`
      ├── load.py        # Prints <role>/role.md
      ├── info.md        # Empty placeholder
      └── role.md        # Empty placeholder
```

## Notes and behavior

- Commands act on the current working directory; run them from the root of the project that owns the roster.
- If a role directory contains `load.py`, `myteam get role` executes it; otherwise it prints `role.md` if
  present. New roles created with `myteam new role` include a `load.py` that prints their `role.md`.
- `myteam get role` defaults to the top-level `.myteam/load.py` if no role name is provided.

## Typical workflow

```bash
myteam init
echo "Your role instructions here" > .myteam/role.md
python .myteam/load.py # Prints top-level instructions plus other role info.md files
```

Running `.myteam/load.py` prints the top-level instructions first, then any `info.md` files found in other role
directories under `.myteam/`.

## License

MIT
