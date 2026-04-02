# `list_skills` Built-In Filter

## Summary

`list_skills` should take a boolean parameter that controls whether built-in skills are included in
its output.

## Problem

Built-in skills such as packaged maintenance or upgrade helpers are not always appropriate to show
in ordinary skill listings.

Right now, callers that want different behavior risk:

- always showing built-in skills, even when they are just support scaffolding
- or hard-coding special-case filtering logic outside `list_skills`

That makes skill discovery harder to control consistently.

## Proposed Change

Add a boolean parameter to `list_skills` so the caller can choose whether built-in skills are
listed.

This should let callers:

- hide built-in skills in normal project skill listings
- include built-in skills in contexts where upgrade or maintenance discovery matters
- keep the filtering decision in one place instead of scattering it across loaders

## Design Questions

- Should built-in skills be included by default or excluded by default?
- Should the parameter mean `include_builtins` or `exclude_builtins`?
- How should `list_skills` determine that a skill is built-in: path convention, metadata, or some
  other marker?
- Does `list_roles` need a matching option, or is this only a skill-listing problem?
