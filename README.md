# Roster

Simple CLI for managing an on-disk roster of agent roles. Roster creates a lightweight structure (`AGENTS.md` plus a `.agents/` directory) that other tools can read to understand available roles and their instructions.

## Features
- Zero-dependency CLI (Python 3.11+)
- Commands to create, remove, and inspect roles
- Works from any directory (operates relative to the current working directory)

## Requirements
- Python 3.11 or newer

## Installation
```bash
pip install roster
```

## Quick start
1) `roster init` — set up `AGENTS.md` and `.agents/` with a default `developer` role.
2) `roster new main` — add your primary role (defaults to `main` when omitted in `whoami`).
3) Edit `.agents/<role>/info.md` and `.agents/<role>/instructions.md` with details for each role.
4) `roster whoami <role>` — print the instructions for that role (or `main` if omitted).

## Commands
| Command | Purpose |
| --- | --- |
| `roster init` | Initialize `AGENTS.md` and `.agents/` with the default `developer` role. |
| `roster new <role>` | Create a new role directory with empty `info.md` and `instructions.md`. |
| `roster remove <role>` | Delete the specified role directory and its contents. |
| `roster whoami [role]` | Print the `instructions.md` for a role (defaults to `main`). |

## What gets created
Running `roster init` produces:

```
AGENTS.md               # Onboarding note for agents
.agents/
  └── developer/
      ├── info.md       # Free-form metadata about the role
      └── instructions.md # The instructions printed by `roster whoami developer`
```

## Notes and behavior
- Commands act on the current working directory; run them from the root of the project that owns the roster.
- If a role directory contains `agent.py`, roster will currently **not execute it**; the CLI only reports that the file exists.
- `whoami` defaults to the `main` role if no role name is provided.

## Typical workflow
```bash
roster init
roster new main
echo "Your role instructions here" > .agents/main/instructions.md
roster whoami main # Run by agent working in project
```

## License
MIT
