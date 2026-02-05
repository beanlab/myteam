#  Roster

An agent roster is a directory of Agent definitions AI coding tools can take advantage of when using multi agent workflows.

## Installation

`pip install roster`

## Usage

To initialize the agent roster, run `roster init`.  This will create the following:


```
AGENTS.md
.agents/
    └──developer/
        └──info.md
        └──instructions.md
```

The `.agents` dir is where agent roles will be defined.  The init script creates an `developer` role which can be modified or deleted if desired.
To create a new role, run `roster new <role>`, which will create a new dir within `.agents` named after the provided role containing empty `info.md` and `instructions.md` files.

The initial `AGENTS.md` file contains the following instructions: Run `roster whoami <role>` with your role.  If you have no role, assume your role is `main`.

When the agent runs `roster whoami <role>` with its role, it's `instructions.md` file will be printed out.  If a `agent.py` file is provided in the agent dir, it will be run instead.
