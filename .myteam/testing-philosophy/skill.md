---
name: Testing Philosophy
description: |
  This skill describes our philosophy towards the kinds of tests we write.
  If you need to read, add, or modify tests, load this skill.
---

Guidance:

- tests should focus on public interface behavior rather than internal implementation details
- tests should prefer high-level use cases that run real application commands in an isolated environment
- assertions should focus on observable results such as exit status, output, and final filesystem state
- private helper tests are secondary and should only be added when a behavior is hard to capture through the interface
- new behavior should be traced back to the interface contract in `governing_docs/application_interface.md`
- tests should act as evidence that the documented interface works as intended
