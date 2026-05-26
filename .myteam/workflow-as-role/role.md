---
name: "Workflow as Role"
description: "demonstrates the desired format of a single-step (default) workflow defined by a role (or skill) file."
workflow-settings:
    agent: codex
    input: 
      file: "the file to evaluate."
    output:
      findings: "list of objects with 'issue' and 'suggested change' for each"
    interactive: true
    fork: false
    usage_logging: summary
    inactivity_timeout_seconds: 900
---

Examine {file} looking for the following:
- are all functions and variables named clearly?
- is there any duplicated logic?

Summarize your findings as output.


