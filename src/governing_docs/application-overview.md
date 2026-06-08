# `myteam` Application Overview

`myteam` is a python framework and CLI for building agent harnesses.

It provides infrastructure support for **skills** and **workflows**.

These documents describe the **interface** and **user experience** of the application. They do not describe how the interface is implemented. 

## Skills

Skills are units of discoverable information that can be loaded on-demand by an agent.

`myteam` allows:

- progressive discovery of hierarchical skills
- dynamic skill-content definition (as opposed to static `.md` files, a python script prints the skill content and can thus bring together or build information at load-time.) 

## Workflows

Workflows are chained, managed agent sessions.

`myteam` supports:

- discoverable, hierarchical workflows (similar to skills)
- input/output schemas 
- session reuse and forking
- multiple agent CLIs
- agent TTY sessions preserved  
- per-session configuration of model, reasoning, and other agent parameters

## Additional Features

In support of these primary concerns, `myteam` also supports:

- `myteam init` - initializing harness configuration (`.myteam` folder)
- `myteam rosters list`, `myteam rosters download` - list and download predefined skills and workflows
- `myteam rosters update` - refresh downloaded content
- `myteam version` - display version

## Scenarios

Files in `scenarios/` describe how this tool is used. 
