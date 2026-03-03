# MyTeam skill Creation

Use the `myteam` CLI for scaffolding skills: `myteam new skill <skill_path>`.  For example, if you wanted to create an
sql skill for a developer agent, your would call `myteam new skill developer/sql`.

## Common Errors

- If you see `ERROR: Cannot find key: <skill>`, you likely ran `myteam new <skill>`. Use `myteam new skill <skill>`.
- Do not edit `AGENTS.md` for skill content. Skills live under `.myteam/<role>/<skill>/`.

## Directory Conventions

- Place skills under the role that uses them, e.g. `.myteam/developer/testing/`.
- Use lowercase names; prefer `-` over `_` unless the project already uses `_`.

## Skill Instructions

After runing `myteam new skill <skill_path>`, `myteam` will create a dir for the skill within the `.myteam` dir.  Within this dir is 3 files: `info.md`,
`load.py`, and `skill.md`. `skill.md` contains detailed instructions on the skill.

### Writing `skill.md`

`skill.md` should contain details on the skill.  This file will be read by the agent adopting the skill, so everything 
applicable to running the skill should be contained here.  When writing, be concise but details. Focus on the specific
actions an agent need to take to perform the skill.  If scripts and other resources are need for the skill, describe
what the resources are and how to use them.

### Writing `info.md`

`info.md` Should be brief, but an agent should be able to understand the types of tasks it should adopt this skill for.
Write `info.md` like a pitch.  Describe the problems the agent can solve with the skill. Don't include information about
how to use the skill.  That will be presented when the agent adopts the skill.

### Required Outputs Checklist

- Skill directory exists at `.myteam/<role>/<skill>/`.
- `info.md` is not placeholder text and clearly describes when to use the skill.
- `skill.md` includes a minimal workflow and handoff guidance (if applicable).

### Verification

After edits, run `myteam get skill <skill_path>` to confirm the new skill renders without placeholder text.

### Templates

Use these as starting points and adjust per project needs.

`info.md` template:

```
Brief description of what the skill enables.

Use this skill for <task types> or when <trigger condition>.
```

`skill.md` template:

```
# <Skill Name>

Use this skill when <context/trigger>.

## Quick Workflow

1. <Step one>
2. <Step two>
3. <Step three>

## Handoff

- If done, report <what to report>.
- If blocked, report <blocker details> and suggest next steps.
```

### Modifying `load.py`

The `load.py` scaffold includes code for presenting the `skill.md` file.  If there is additional setup required for the
skill (like loading a venv environment, setting env vars, or preloading references), update the file to include that logic.
