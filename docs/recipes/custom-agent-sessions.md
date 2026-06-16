# Custom Agent Sessions

The problem with `AGENTS.md` is that **every** agent working in your project (including delegated agents) reads and follows it. 

If you are trying to maintain separate context and instructions for separate agents, `AGENTS.md` is an antipattern.

Instead of `AGENTS.md`, create Markdown workflow files to represent each role you want. Then simply `myteam start` that file to launch the agent. 