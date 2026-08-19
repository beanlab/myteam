---
type: workflow
description: An agent assistant. Delegate specific, scoped tasks to this agent as needed, especially when fresh context is important to the task. 
usage: If a different model is requested, specify it e.g. `--model 'openai/gpt-5.6-sol'` (assume `openai/` unless specified). 
input: 
  instructions: (str) What you would like done. Include context and all other relevant information. Include what you want included in the output result.
output:
  result: (str) The text requested in the input instructions.
---

{{ instructions }}
