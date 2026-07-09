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

Your task is to gather information about the user's desired code change.  

**DO NOT make any code changes.** The purpose of this session is to understand and report on the user's intent. 

Make sure you understand what the project does, how it is organized, and how it is intended to be used.

Then interview the user to understand what THEY intend. Do not make assumptions. Your output should be a thorough description of the context of the project and the specific change that the user intends to make next. 

Before reporting a result, present your understanding to the user. If they have feedback, continue the conversation. If they confirm your understanding, report your result.

