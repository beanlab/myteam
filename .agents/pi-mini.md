---
type: workflow
agent: pi
model: openai/gpt-5.4-mini
---

{{ read_file('dev/general-instructions.md') }}

{{ read_file('dev/myteam-assistant-instructions.md.jinja') }}

{{ read_file('dev/code-planning.md') }}

{{ read_file('dev/code-style.md') }}
