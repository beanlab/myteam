# TODO: Public Interface Process

Design and implement a process for documenting and evolving the public interface of `myteam`.

This should establish an interface document as the contract for behavior, the source for high-level tests, and the target for implementation work.

The process should cover:

- how the public interface of `myteam` is defined and documented
- which commands, outputs, filesystem effects, and loader behaviors are part of that interface
- how proposed feature work updates the interface document before implementation begins
- how tests are derived from the interface document
- how implementation is validated against the documented interface
- how interface changes are reviewed and communicated
- when a change is considered a public interface change versus an internal refactor

This process should include an explicit rule:

- new features should begin by modifying the interface document first
- that document should act as the contract for tests and the target for implementation

This rule should also be captured in a `.myteam` skill so agents working in this repo are instructed to update the interface contract before implementing new public behavior.

This document is intentionally a placeholder until the interface process is designed.
