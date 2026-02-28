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

1) `myteam init` — set up `AGENTS.md` and `.myteam/` with a default `main` role (creates `.myteam/main/agent.py` plus
   templated `info.md`/`role.md`).
2) `myteam new developer` — add another role (optional).
3) Edit `.myteam/<role>/info.md` and `.myteam/<role>/role.md` with details for each role (new roles start empty;
   main starts with templates).
4) `myteam get-role <role>` — run the role’s `agent.py` (if present) or print `role.md` (defaults to `main` when
   omitted).

## Commands

| Command                  | Purpose                                                                                                                          |
|--------------------------|----------------------------------------------------------------------------------------------------------------------------------|
| `myteam init`            | Initialize `AGENTS.md` and `.myteam/` with the default `main` role (with `agent.py`, templated `info.md` and `role.md`). |
| `myteam new <role>`      | Create a new role directory with `agent.py`, empty `info.md`, and `role.md`.                                             |
| `myteam remove <role>`   | Delete the specified role directory and its contents.                                                                            |
| `myteam get-role [role]` | Print the `role.md` for a role (defaults to `main`).                                                                     |

## What gets created

Running `myteam init` produces:

```
AGENTS.md               # Onboarding note for agents
.myteam/
  └── main/
      ├── agent.py        # Prints main instructions plus info.md for other roles
      ├── info.md         # Pre-populated main role metadata template
      └── role.md # Pre-populated main role instructions template
  └── <new-role>/        # Created by `myteam new <role>`
      ├── agent.py        # Prints <role>/role.md
      ├── info.md         # Empty placeholder
      └── role.md # Empty placeholder
```

## Notes and behavior

- Commands act on the current working directory; run them from the root of the project that owns the roster.
- If a role directory contains `agent.py`, `myteam get-role` executes it; otherwise it prints `role.md` if
  present. New roles created with `myteam new` include an `agent.py` that prints their `role.md`.
- `get-role` defaults to the `main` role if no role name is provided.

## Typical workflow

```bash
myteam init
echo "Your role instructions here" > .myteam/main/role.md
python .myteam/main/agent.py # Prints main instructions plus other role info.md files
```

Running `.myteam/main/agent.py` prints `main` instructions first, then any `info.md` files found in other role
directories under `.myteam/`.

## License

MIT
