# Backlog Grooming Skill

## Summary

Add a dedicated backlog-and-grooming skill that teaches agents how to write backlog documents, how to
groom the backlog consistently, and how to maintain a project-level view of backlog dependencies and
priorities.

This is not just a one-time documentation task. The intent is to create a repeatable operating
process so backlog work stays readable, comparable, and actionable as the backlog grows.

## Problems

### Backlog items do not yet have an explicit authoring standard

The existing backlog documents are generally coherent, but the repo does not yet define:

- when a backlog item should exist instead of a feature plan
- what sections a backlog document should include
- how much implementation detail is appropriate at backlog stage
- how backlog items should refer to related work or dependencies

That makes the quality of backlog docs depend too much on local judgment.

### There is no explicit grooming process

Backlog items currently accumulate as design notes, but there is no maintained process for:

- reviewing older items for staleness
- splitting oversized items
- merging duplicates
- identifying prerequisite relationships
- identifying which items are most urgent or strategically important

Without grooming, the backlog becomes harder to use as a planning tool.

### Dependencies and priorities are not tracked in one place

Some dependencies are mentioned inside individual backlog docs, but there is no single maintained
document that answers questions such as:

- what items block other items
- what work can proceed independently
- which backlog items are highest priority right now
- which items are design follow-ups versus implementation-ready work

That forces readers to reconstruct planning state from scattered notes.

## Goals

- Provide a built-in or project skill that teaches agents how to create and maintain backlog docs.
- Standardize the expected format and scope of backlog documents.
- Define a repeatable grooming workflow for reviewing and updating backlog items.
- Maintain a dedicated document that tracks backlog dependencies, sequencing, and priorities.
- Keep backlog documentation lightweight enough to maintain, while still useful for planning.

## Proposed Change

### Add a backlog-and-grooming skill

Create a skill that agents load when they are:

- writing a new backlog item
- updating an existing backlog item
- grooming the backlog
- planning cross-cutting design work

The skill should explain:

- when to create a backlog doc versus a feature plan
- the standard structure for backlog docs
- how to describe scope boundaries and open questions
- how to record follow-up work without turning backlog docs into implementation transcripts
- how to update the backlog dependency/priority tracker

### Standardize backlog doc format

The skill should define a preferred format for backlog documents. A reasonable baseline is:

- `Summary`
- `Problems` or `Problem`
- `Goals`
- `Proposed Change` or `Proposed Direction`
- `Scope Boundaries`
- `Open Questions` or `Open Follow-Up Work`

Not every document must use identical section names, but the skill should define the expected shape
and purpose of each section so backlog items remain comparable.

### Define a backlog grooming process

The skill should define a recurring grooming workflow such as:

1. Review recently added backlog docs.
2. Check older docs for staleness or changed assumptions.
3. Merge duplicates or split overloaded items.
4. Identify prerequisite relationships and sequencing constraints.
5. Assign or revise priority labels or ordering.
6. Update the dependency/priority tracker to reflect the current view.

The process should also explain what kinds of edits belong in a grooming pass versus requiring
separate feature design work.

### Maintain a dependency and priority tracker

Add a dedicated governing doc that summarizes backlog relationships in one place.

That tracker should make it easy to answer:

- which items are top priority
- which items are blocked by other items
- which items are prerequisites for broad roadmap themes
- which items are still exploratory versus ready for feature planning

The tracker can stay lightweight, but it should be authoritative enough that agents do not need to
infer roadmap state from scattered backlog prose.

## Scope Boundaries

- This item is about backlog process and documentation quality, not about implementing any specific
  product feature.
- This does not require a heavy project-management system or external tooling.
- This does not require every existing backlog doc to be rewritten immediately, though some cleanup may
  be needed as part of adoption.

## Open Questions

- Should the backlog-and-grooming skill be packaged as a built-in skill, a project-local skill, or
  both?
- Should the dependency/priority tracker use simple prose sections, a table, or a structured YAML-like
  format?
- Should priorities be expressed as ordered lists, named buckets, or explicit status markers such as
  `exploratory`, `ready`, and `blocked`?
- How often should backlog grooming be expected: opportunistically during related work, or as a
  dedicated recurring maintenance task?
