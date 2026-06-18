# Using `myteam`

*This document gives you a **why** overview of `myteam`. The rest of `governing_docs/` give you the technical **how** of `myteam`.*

## Harness

A harness is the way you run an agent or team of agents. The task of the harness is to manage the information—or context—available to an agent session. 

Information can be stored and indexed in a way that the agent knows it is there and can look it up on demand. This is the principle of **progressive disclosure**. `myteam` **skills** enable effective progressive disclosure.

Information can be prepared in advance and supplied to the agent in the initial prompt. This is the principle of **prework**. `myteam` **workflows** enable effective prework.

## Using Skills 

Build a skill when there is information an agent needs to do a specific task or work in a specific domain, but when you don't know at runtime whether the agent will be working in that domain.

For example, in your project you use a specific framework for your UI, and if an agent is going to touch the UI, it should read your UI instructions. But when you start the session, you don't know if the agent will touch the UI or not—that depends on whether the bug you are seeing is frontend or backend. After the agent identifies the source of the bug as frontend, it loads the UI instructions before touching the code.

Progressive disclosure is helpful because it avoids bloating your context with irrelevant information. The more information that is in the agent's context, the less attention the agent can give to any one piece of information.

You don't want the agent getting distracted from what matters because it is inundated with information that doesn't matter.

Progressive disclosure also avoids wasting tokens: you don't pay to read information you don't need. 

### How Skills Work

A skill is essentially a body of text with a name and a description. The name and description of the skill are provided to the agent in the initial context. When the agent decides it needs the skill, it then loads the text.

### Hierarchical Skills

Most agents support skills out-of-the-box. However, these systems store all skills in a single folder with no hierarchy. As available skills accumulate, the original problem returns: we now have too many skill descriptions bloating our context.

`myteam` lets you store your skills in folders, giving each folder a description stored in a file named `description.md`. The agent can then decide when it needs to list the skills in that folder. By organizing your skills by domain, you can achieve logarithmic complexity instead of linear complexity in your context usage. 🏆

### Dynamic Skills

Classic skills are static content. They often include instructions like "read these other files" or "read this URL" or "first use this tool to get needed information".

An agent then reasons about the instructions, decides it needs a tool call, calls the tool, and then considers the result. This takes time, spends tokens, and might fail if the agent doesn't follow your instructions.

The principle of **determinism** is that if a job can be in code, do it in code. Don't rely on agent reasoning for anything that can be done in code. 

So if we know that the agent will read a file, then let's read the file in code and inject the content directly into the initial prompt. Fewer tokens. Less time. Always works.

`myteam` skills can be `.py` files as well as the classic `.md` files. These are invoked by `myteam` and the stdout becomes the skill body. You put whatever logic you need to creat the content you want. 

Reading files, listing directories, reading URLs, and loading data are common use-cases for dynamic skills. For example, you need a skill that describes how to use a CLI tool: include a call to `--help` in the skill content so the agent knows the usage up front.

## Using Workflows

Agents perform best when they are given a single task to do with only the information needed for that task.

Classic agent usage relies on agent reasoning to determine what information is needed. We supply agents with instructions to tell them what information they should find, but leave it to them to reason about the instructions and decide to follow them. Your mileage will vary.

**Prework** flips this model. If you know an agent should consider a detail before moving to the next step, write a workflow with two sessions: in the first it considers the detail, in the second it acts on the information.

Importantly, I can include instructions for the first step that are unique to only that step, and that should be absent from later steps; and likewise for any step. Workflows allow you to control what information is available to an agent at each step of a process.

### Markdown Workflows

Use Markdown workflows for session roles and simple workflows. 

Instead of a single `AGENTS.md` that all agents use, define your various agent roles as separate `.md` workflows. `myteam start` the role you want for that session.

For example, you might have separate roles for planning, implementing, reviewing, documenting, etc.  

All Markdown bodies are rendered with jinja2. The environment comes with `read_file` so you can import content from other files and thus compose single documents from multiple sources.

You can also use the `myteam_explain()` to include instructions to your agent about how to use skills and workflows and `myteam_list(dir)` to list skills and workflows in the specified directory, the controlling which agents can use skills and workflows and which skills and workflows are visible to it.

### Defining Outputs

When you give an agent a defined output schema, it's prompt automatically includes the output schema along with instructions for how to use `myteam result` to report that output.

Given an agent an output schema when:

- you want to guide its work towards a constrained result
- you want to extract structured information from the session
- you want to give the agent the ability to conclude the session

Agents love to fill out forms. You can craft your output in a way that as they fill it out, it guides them towards a more reliable conclusion. For example, consider:

```yaml
output:
  observations: ["observations about the code"]
  relevant: ["include only the observations that pertain to our task"]
  summary: "a summary of the relevant observations"
  conclusion: "is this ready for deployment?"
```

This output leads the agent through the desired process of coming to a well-reasoned conclusion.

If you want to share information from one session with code or another agent, specify the information you need in the output schema. You can then inject these values into the prompt of a downstream agent or process them with code.

When an agent reports the output via `myteam result`, the session automatically closes. Thus, agents can determine when an interactive conversation has fulfilled the objective and move to the next step of the workflow. 

If you want an agent to be able to report information but not end the session, use the resuming-session feature.

### Resuming Sessions

`run_agent` returns a `SessionResult` object which contains the session ID. Passing that ID to another `run_agent` invocation will resume the specified session.

This is particularly useful if you want to release information progressively for a single agent run. For example, if you don't want to provide information about the next step until an objective is complete: require information about the first objective in the first session's output, then launch the second session with a new prompt resuming the first session; the session will resume (all the context preserved) but with the new prompt included. 

Resuming sessions allows you to limit unnecessary information early in the conversation, providing it automatically when the conversation advances. Fewer tokens along the way. Better focus at each step of the process. 

You can also use `fork=True` to fork a session: a new session is made from a copy of the prior session's context.

### Workflows as Tools

Workflows are also discoverable resources like skills. The description field in workflow frontmatter describes to an agent when and how to invoke a workflow. 

When launched, the current workflow pauses while the inner workflow runs. When the inner workflow completes, all information reported via `report_workflow_result` is displayed to the caller. Thus, workflows can function like tool calls. 

## Guidance

If you need to provide agents with information on demand, use skills.

If you have too many skills in your context, organize them in folders.

If you need dynamic skill content, use `.py` skills.

If you need a sequence of steps performed reliably, use workflows.

If you want defined outputs from a session, use workflows.

If you want defined roles for different sessions, use workflows. 

If you want to release information one stage at a time, resume prior sessions with a workflow.

