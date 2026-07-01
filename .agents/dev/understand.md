---
type: workflow
agent: pi
model: openai/gpt-5.4-mini
description: Gathers information to understand a change request
output:
    context: What does this project do?
    change: What specific change is being requested?
    why: What is the reason for this change? Why is this change important?
    remember: What aspects of the project should we keep in mind as we consider this change?
---

After you have read these instructions, say Ready.

--- CONTEXT ---

{{ read_file('general-instructions.md') }}

--- PROJECT DESCRIPTION ---

{{ myteam_onboard() }}

--- TASK ---

# Task: Understand the Change Request

Gather information about the user's desired code change. 

DO NOT make any changes. 

Make sure you understand what the project does, how it is organized, and how it is intended to be used.

Interview the user to understand what THEY intend. Do not make assumptions. 

Before reporting a result, present your understanding to the user. If they have feedback, continue the conversation. If they confirm your understanding, report your result.
