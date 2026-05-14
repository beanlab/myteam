---
name: Development Workflow Scenario Documentation
description: |
  Local development-workflow guidance for creating, editing, and organizing
  scenario-style documentation for externally observable application behavior.
  Load this skill before scenario conversation or scenario artifact work.
---

# Scenario Documentation

Scenario documentation is the authoritative documentation model for externally
meaningful system behavior.

Use it to document how the application behaves at real-world interfaces:

- user-visible behavior and workflows
- operational contracts and configuration surfaces
- externally observable validation, failures, side effects, and state
  transitions
- integration boundaries and runtime assumptions that users, operators,
  deployers, or downstream systems must honor

Do not use scenario documentation for internal code structure, private helper
behavior, speculative future behavior, or implementation details that do not
affect the external contract.

## What A Scenario Is

A scenario is a human-readable, implementation-independent behavioral
guarantee. It describes:

- the relevant context
- the triggering action
- the observable outcomes the system must guarantee

Tests validate scenarios. Implementations satisfy scenarios. Behavior must not
exist only in tests.

## Documentation Tree

Scenario documentation is organized as a semantic file tree. Directory placement
communicates capability boundaries, behavioral grouping, shared context, and
discoverability.

Prefer domain-oriented hierarchy:

```text
scenarios/
  registration/
  conversation/
  assignment_feedback/
  operations/
```

Avoid implementation-oriented hierarchy:

```text
scenarios/
  utils/
  services/
  helpers/
```

Parent directories may include a `README.md` or index document that defines
shared terminology, assumptions, domain context, and links to child scenarios.
Child scenario files inherit that context implicitly and should not repeat it
unnecessarily.

## Authoring Rules

Each scenario file should define one externally observable behavioral guarantee.

Each scenario must be:

- human-readable
- implementation-independent
- atomic
- externally verifiable
- directly testable

Focus on:

```text
What behavior must the system guarantee in this situation?
```

Avoid classes, internal functions, storage mechanisms, framework details, and
algorithm choices unless they are themselves contractual guarantees.

## Scenario Template

```md
# <Scenario Title>

## Purpose (Optional)

<10 words or less explaining the capability>

---

# Context

<Relevant system state, actors, inputs, permissions, and assumptions>

---

# Action

<Triggering interaction>

---

# Interaction (Optional)

| Action | Outcome |
| --- | --- |
| <Context-relative action or state> | <Observable response> |

---

# Outcome

<Observable required outcomes>

---

# Non-Goals (Optional)

<Explicit exclusions>

---

# Related Scenarios

<Optional repository-relative references>
```

## Interaction Tables

Use an `Interaction` section when one atomic scenario is best described as an
ordered series of externally visible exchanges or tightly related variants of
one capability.

Interaction tables must use exactly these columns:

```md
| Action | Outcome |
| --- | --- |
```

Rows should be concise and context-relative. Do not repeat actors, channels,
command surfaces, or system names already established by `Context` and `Action`.

Do not split a scenario only because it has multiple related command forms,
validation branches, or workflow phases. If the variants belong to one
user/operator capability, keep them in one scenario and use an `Interaction`
table.

Split only when rows describe different behavioral contracts that would
naturally be discovered, tested, or maintained separately.

## Naming

Scenario filenames must be lowercase, use underscores, and describe behavioral
guarantees.

Prefer:

```text
verb + behavioral outcome
```

Examples:

```text
rejects_invalid_schema.md
closes_session_after_completion.md
preserves_feedback_submission.md
```

## Refactoring Scenarios

Refactor scenario documentation when the tree no longer makes behavior easy to
find, maintain, or verify.

Do not lose information. When moving, splitting, or converting prose to
interaction tables, preserve every behavioral guarantee, context, action,
outcome, non-goal, related scenario, and shared assumption.

Keep hierarchy semantic. Organize by externally meaningful capability or
operational concern, not internal module layout.

## Quality Checklist

Before finalizing a scenario, verify:

- Is the behavior atomic?
- Is the behavior observable?
- Is every outcome testable?
- Is implementation detail minimized?
- Is the scope narrow?
- Does the filename describe the guarantee?
- Does the scenario avoid ambiguity?
- Does any `Interaction` table avoid repeating context from surrounding
  sections?
- Could a test be written directly from this file?
- Could another engineer implement the behavior from this file alone?
