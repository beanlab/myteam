# `myteam` Philosophy

The fundamental principles of `myteam` are:

- determinism over agent decisions whenever possible
- progressive disclosure of resources
- context isolation

## Determinism Over Decisions

Agents are incredible in their ability to make decisions. Through reasoning and tool-calling, they can shape their context to meet the needs of the task at hand.

However, this comes at a cost: in tokens, time, and reliability. If you know an agent will need some set of instructions for the task, why pay for an agent to reinvent the wheel or rediscover the instructions? `myteam` provides simple infrastructure for building up the context for an agent session **before** the agent starts. No tokens spent deciding the obvious. No turns wasted exploring the system. No missed skill triggers. 

This extends also to skills: why ask an agent in Markdown to read all the documents in a folder when a python script could trivially build that context up front and the agent hits the ground running? `myteam` supports both classic Markdown skill as well as Python skills: scripts that produce the skill content dynamically.

## Progressive Disclosure

Just as we organize our code, we need to organize the information our agents use. Massive flat lists of every skill available to an agent bloat context, distract agents, and waste tokens. 

`myteam` allows you to organize skills and workflows hierarchically. Agents can navigate the directory tree to find the skills they need, but with logarithmic instead of linear complexity.

## Context Isolation

Agents do best when they can focus on specific tasks. Developers need harnesses that allow for separate, defined contexts for each agent, with the ability to move only the necessary information across those boundaries. `myteam` workflows make chaining agents across separate contexts trivial. 

