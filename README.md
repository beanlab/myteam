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
1) `myteam init` — set up `AGENTS.md` and `.agents/` with a default `main` role.
2) `myteam new developer` — add another role (optional).
3) Edit `.agents/<role>/info.md` and `.agents/<role>/instructions.md` with details for each role.
4) `myteam get-role <role>` — print the instructions for that role (or `main` if omitted).

## Commands
| Command | Purpose |
| --- | --- |
| `myteam init` | Initialize `AGENTS.md` and `.agents/` with the default `main` role. |
| `myteam new <role>` | Create a new role directory with empty `info.md` and `instructions.md`. |
| `myteam remove <role>` | Delete the specified role directory and its contents. |
| `myteam get-role [role]` | Print the `instructions.md` for a role (defaults to `main`). |

## What gets created
Running `myteam init` produces:

```
AGENTS.md               # Onboarding note for agents
.agents/
  └── main/
      ├── info.md       # Free-form metadata about the role
      └── instructions.md # The instructions printed by `myteam get-role main`
```

## Notes and behavior
- Commands act on the current working directory; run them from the root of the project that owns the roster.
- If a role directory contains `agent.py`, myteam will currently **not execute it**; the CLI only reports that the file exists.
- `get-role` defaults to the `main` role if no role name is provided.

## Typical workflow
```bash
myteam init
echo "Your role instructions here" > .agents/main/instructions.md
myteam get-role main # Run by agent working in project
```

## License
MIT
