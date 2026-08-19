- make sure `myteam start` called by an agent tool works correctly
- workflow descriptions include usage instructions
- support pydantic for output, with validation
- fix usage
- reserve banner in terminal view for workflow messages
- print usage only on master `myteam start` invocation
- command-line args to override md workflow settings (agent, model, reasoning, interactive)
- print session titles on start and resume to orient the user
- new_workflow.py template
- strip transcript from error messages (it floods the terminal)
- make sure workflow outputs don't print transcript either in template
- instructions/principles for agent to build workflows
- 3rd party skills/workflows as python packages
- start a skill like you do a Markdown workflow
- `myteam start <workflow.md> --fork` forks the current session and injects the specified prompt; not sure this makes sense for python workflows, but does work for MD workflows.  
- expose workflow-level transcripts for debugging (decide UX)
- prompt_file arg for run_agent
- pydantic support
- figure out a way for simple sub-session bulk-prompting - i.e. pass a single string to stdin that is included as `{{ input }}`. Maybe the named values come as `--args`?

# Harnesses

- interaction instructions
- scratch space instructions

- backlog
- plan + review
- docs + review
- design + review
- tests + review
- implementation prework + review
- implement + review
- review result
- user docs
- changelog

- spring cleaning