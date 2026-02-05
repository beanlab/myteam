# Myteam

Simple CLI for managing an on-disk roster of agent roles. Myteam creates a lightweight structure (`AGENTS.md` plus a `.agents/` directory) that other tools can read to understand available roles and their instructions.

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
1) `myteam init` — set up `AGENTS.md` and `.agents/` with a default `main` role (creates `.agents/main/agent.py`).
2) `myteam new developer` — add another role (optional).
3) Edit `.agents/<role>/info.md` and `.agents/<role>/instructions.md` with details for each role.
4) `myteam get-role <role>` — print the instructions for that role (or `main` if omitted).

## Commands
| Command | Purpose |
| --- | --- |
| `myteam init` | Initialize `AGENTS.md` and `.agents/` with the default `main` role (with `agent.py`). |
| `myteam new <role>` | Create a new role directory with `agent.py`, empty `info.md`, and `instructions.md`. |
| `myteam remove <role>` | Delete the specified role directory and its contents. |
| `myteam get-role [role]` | Print the `instructions.md` for a role (defaults to `main`). |

## What gets created
Running `myteam init` produces:

```
AGENTS.md               # Onboarding note for agents
.agents/
  └── main/
      ├── agent.py        # Prints main instructions plus info.md for other roles
      ├── info.md         # Free-form metadata about the role
      └── instructions.md # The instructions printed by `myteam get-role main`
```

## Notes and behavior
- Commands act on the current working directory; run them from the root of the project that owns the roster.
- If a role directory contains `agent.py`, `myteam get-role` will execute it; otherwise it prints `instructions.md` if present. New roles created with `myteam new` include an `agent.py` that prints their `instructions.md`.
- `get-role` defaults to the `main` role if no role name is provided.

## Typical workflow
```bash
myteam init
echo "Your role instructions here" > .agents/main/instructions.md
python .agents/main/agent.py # Prints main instructions plus other role info.md files
```

Running `.agents/main/agent.py` prints `main` instructions first, then any `info.md` files found in other role directories under `.agents/`.

## License
MIT
