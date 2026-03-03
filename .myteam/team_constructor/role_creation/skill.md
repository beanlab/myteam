# MyTeam Role Creation

Use the `myteam` CLI for scaffolding roles: `myteam new role <role_path>`.  For example, if you wanted to create a top
level developer role, your would call `myteam new role developer`.  `myteam` also supports nested agents.  To create a
nested agent, describe the path for the agent.  For example, if you were to create a ui developer role and the top level
developer role already existed, you would call `myteam new role developer/ui`.

## Common Errors

- If you see `ERROR: Cannot find key: <role>`, you likely ran `myteam new <role>`. Use `myteam new role <role>`.
- Do not edit `AGENTS.md` for role content. Role metadata lives in `.myteam/<role>/info.md` and `.myteam/<role>/role.md`.

## Role Instructions

After runing `myteam new role <role_path>`, `myteam` will create a dir for the role within the `.myteam` dir.  Within this dir is 3 files: `info.md`,
`load.py`, and `role.md`. `role.md` contains core logic for the agent while `info.md` contains information about how to
use the role.  In other words, `role.md` is for the role, and `info.md` if for whomever delegates to the role.

### Writing `role.md`

`role.md` should be detailed yet concise.  It should focus on how the agent should behave, how it should interact with
the codebase, and what it's deliverables are.  A `role.md` file should sound like a job description.  Agent roles should
also be focused, don't give the agent more than one responsibility.

### Writing `info.md`

`info.md` Should be brief.  It should contain only what the supervising agent needs to know to delegate to the new role.
Be sure to include information about what the agent needs to function, how it should be called, and what the supervising
agent should expect as an output.

### Required Outputs Checklist

- Role directory exists at `.myteam/<role>/`.
- `info.md` is not placeholder text and includes handoff guidance.
- `role.md` includes role duties and handoff criteria.

### Verification

After edits, run `myteam get role <role>` to confirm the new role renders without placeholder text.

### Templates

Use these as starting points and adjust per project needs.

`info.md` template:

```
A brief, concrete description of the role and what it owns.

Hand off to this role for <task types>. Hand off back once <done criteria> or when <decision needed>.
```

`role.md` template:

```
## Your Role

You are the <Role Name> for this project. Describe your core responsibilities.

## How To Work

- Read existing code and tests before changing behavior.
- Prefer minimal changes that satisfy the requirement.
- Add or update tests when behavior changes.
- Update docs/config when required by the change.
- Flag unclear requirements or risky assumptions early.

## Handoff

- Handoff to the team lead when a change is ready for review, or when you need a decision on scope, priority, or product behavior.
- If blocked by missing context or access, report the blocker and suggest the next best step.
```

### Modifying `load.py`

In most cases, `load.py` should not need to be modified.  'load.py' is a script describing how `role.md` should be presented
to the agent.  The only cases it should be modified is if there is extra functionality that is needed when the role is
loaded.  
