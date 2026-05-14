# Discovers Codex Session From Recent Nonce

## Purpose

Identify new sessions.

---

# Context

A workflow step starts a new Codex session. Codex records session transcripts as
rollout files under the user's Codex sessions directory, and each rollout
filename contains the Codex session UUID.

---

# Action

The workflow runtime starts Codex with a generated nonce embedded in the prompt
and then asks the selected Codex agent config to discover the session ID after
the session exits.

---

# Outcome

The generated nonce is unique enough for session discovery and is expected to be
a UUID or similarly specific token. The Codex agent config searches Codex
rollout files from newest to oldest, checks each candidate for the nonce, stops
at the first matching rollout, and parses the session ID from that rollout
filename.

In the normal case, the matching rollout is one of the newest files, so
discovery should only need to inspect the most recent file or the next few
recent files before finding the nonce. The search must not continue through
older files after a matching rollout has been found.

If no rollout file contains the nonce, the config reports a useful lookup
failure instead of returning an unrelated session ID.

---

# Non-Goals

This scenario does not require full workflow session reuse. It only defines how
a newly started Codex session is identified after the run.

---

# Related Scenarios

- `src/governing_docs/scenarios/workflow/agent_runtime_configs/resolves_agent_config.md`
