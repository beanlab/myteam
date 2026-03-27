# Trusted Content Verification Framework

## Summary

Downloaded `myteam` content should carry explicit verification state. Unverified downloaded content
must not be loaded directly through `myteam get role ...` or `myteam get skill ...`.

Instead, `myteam get ...` should detect that the target node belongs to unverified downloaded
content and return instructions telling the current agent to delegate review to a built-in verifier
role, then reload the original node after verification succeeds.

When downloaded content is updated, its verification state should revert to unverified.

This keeps runtime loading local-only while adding a review gate between "content exists on disk"
and "agents are allowed to execute its `load.py`."

## Problem

The current backlog around downloads and trust is too thin for the actual risk.

Today:

- `myteam download` writes remote content into the local tree
- `myteam get ...` executes `load.py` from the resolved node
- there is no verification state between download and execution

That means downloaded content becomes executable agent instruction immediately after installation.

The problem gets sharper once updates exist:

- a subtree that was previously reviewed can change on update
- the new content should not inherit the old review status
- agents need a standard path for re-verification

## Goals

- Require explicit verification before downloaded content can be loaded.
- Reset verification state after any update that changes managed content.
- Keep the trust boundary local and inspectable.
- Route review work through a built-in verifier role rather than ad hoc project instructions.
- Make `myteam get ...` enforce the gate consistently for downloaded roles and skills.
- Preserve the existing local filesystem execution model once content is verified.

## Non-Goals

- Cryptographic signing as the only trust mechanism.
- Automatic semantic review of downloaded content.
- Dynamic remote checks during `get role` or `get skill`.
- Silently executing unverified content with only a warning.

## Core Model

Downloaded content moves through explicit states:

1. `unverified`
2. `verified`
3. `stale`

Practical simplification:

- `stale` can be represented as `unverified` with a reason such as `updated`

The important rule is:

- only `verified` content may be executed through `myteam get ...`

## Verification Unit

Verification should attach to a downloaded managed subtree, not only to individual files.

That subtree is the same natural unit introduced by the download/update design:

- one downloaded roster or subtree install
- one metadata file at its root
- one provenance record
- one verification status record

This keeps trust state aligned with provenance and update operations.

## Metadata Model

Extend the download metadata file, or add a sibling trust file, with fields such as:

- source repo
- source path or roster
- source ref
- installed timestamp
- installed content fingerprint
- verification status
- verification timestamp
- verifier identity or note
- verification basis
- status reason

A single hidden file such as `.myteam-source.yml` can hold both provenance and verification data if
that stays readable.

Suggested trust fields:

```yaml
verification:
  status: unverified
  reason: downloaded
  content_fingerprint: abc123
  verified_at:
  verified_by:
  basis:
```

When content is updated and the fingerprint changes:

- `status` becomes `unverified`
- `reason` becomes `updated`
- previous verification facts are cleared or retained only as history, not as active status

## `myteam get ...` Gate

`myteam get role ...` and `myteam get skill ...` should check verification status before executing
`load.py` for downloaded content.

Behavior:

- if the node is project-authored and not managed by download metadata, proceed normally
- if the node is downloaded and verified, proceed normally
- if the node is downloaded and unverified, do not execute its `load.py`

Instead, `myteam get ...` should print a blocking instruction message describing:

- that the requested content is downloaded and unverified
- which managed subtree owns it
- why it is unverified, such as `downloaded` or `updated`
- that the agent must delegate to the built-in verifier role
- that the agent should reload the original requested node after verification completes

This keeps the trust policy in the CLI, not in ad hoc project prompts.

## Built-In Verifier Role

Verification should be handled by a built-in role dedicated to reviewing unverified downloaded
content.

Desired behavior:

- `myteam` ships a built-in verifier role
- the role receives the target subtree and provenance context
- the role guides an agent through inspecting the downloaded content and deciding whether to mark it
  verified

This is intentionally a role, not only a skill, because the task is a distinct responsibility:

- review downloaded content
- decide whether it is acceptable to admit into the live instruction tree
- update verification state accordingly

Example instruction flow from `myteam get skill vendor/foo`:

1. Agent runs `myteam get skill vendor/foo`
2. `myteam` detects the owning downloaded subtree is unverified
3. `myteam` prints instructions such as:
   `Content for 'vendor/foo' is unverified. Delegate to built-in role 'builtins/verifier' with the managed subtree path and then rerun 'myteam get skill vendor/foo'.`
4. The agent delegates review to the verifier role
5. The verifier role reviews and, if approved, marks the subtree verified
6. The original agent reruns `myteam get skill vendor/foo`

## Built-In Role Packaging

Current architecture has packaged built-in skills, not packaged built-in roles.

This backlog item therefore implies one of:

- add a packaged built-in role mechanism parallel to built-in skills
- or broaden the provider design so built-in roles and skills can both be packaged

The verification design should not force the implementation detail yet, but the product requirement
is clear:

- there must be a built-in verifier role available without requiring projects to author it manually

That built-in role may later share the same provider/resolver architecture as built-in skills.

## Verification Workflow

The verifier role should guide an agent through checks such as:

- inspect provenance metadata
- inspect diff against prior verified version if this is an update
- inspect `load.py`, instruction files, and tools in the subtree
- look for unexpected executables, shell bootstraps, or suspicious environment setup
- decide whether to approve, reject, or escalate to the user

If approved:

- write updated verification metadata

If rejected:

- leave status as unverified or mark as rejected
- explain why the content should not be loaded

## Update Behavior

After `myteam update` modifies a managed subtree:

- verification status must revert to unverified
- the reason should indicate update or changed fingerprint

This should happen even if:

- the source repo is the same
- the target path is the same
- the previous version was verified

Trust attaches to reviewed content, not only to the source location.

## Scope Boundaries With Download Design

This work should integrate with the download/update provenance design rather than replace it.

Expected relationship:

- `download.md` defines install metadata and update flow
- this trust design adds verification state and load gating on top of that metadata

The rule in `download.md` that "`get role` and `get skill` remain unchanged" should be revised.
They should remain local-only and filesystem-based, but they should gain trust-state enforcement.

## Failure and UX Policy

Unverified content should be blocked, not warned.

Recommended behavior for blocked loads:

- exit non-zero
- print the verifier-delegation instructions on stdout or stderr in a form an agent can act on
- include the exact command to rerun after verification

The important thing is that the message be operational, not just diagnostic.

## Open Design Choice: Role vs Skill

The request here prefers a built-in verifier role, which is sensible because review is a distinct
responsibility.

One alternative would be:

- keep a built-in verifier skill
- tell the current agent to load that skill and perform verification itself

That is weaker operationally because it does not create a clean handoff boundary.

Recommended direction:

- use a built-in verifier role

## Security Notes

This feature changes the effective execution boundary:

- downloaded content is no longer executable merely because it exists on disk
- execution now depends on explicit local verification state

That is a substantial safety improvement even before introducing signatures or stronger provenance
checks.

However, verification metadata itself becomes sensitive. We should assume:

- only explicit verifier actions can mark content verified
- updates cannot preserve prior verification automatically when content changes
- manual local edits to metadata are possible and should be treated as outside the automated trust
  guarantee

## Implementation Plan

### Phase 1: metadata and gating

- extend managed subtree metadata with verification state
- teach `download` to initialize downloaded content as unverified
- teach `update` to reset verification state after content changes
- teach `get role` and `get skill` to block unverified downloaded content before executing `load.py`

### Phase 2: built-in verifier role

- add packaged built-in role support if needed
- ship a verifier role with clear review instructions
- ensure the blocking `get ...` message points to that role

### Phase 3: review ergonomics

- provide diff or tree-summary tools to help the verifier role inspect content
- optionally add commands for marking verification outcomes in a structured way
- consider history or audit logging for repeated updates

## Open Questions

- Should verification state live inside the existing download metadata file or a separate trust file?
- Should rejected content have a separate explicit status from unverified?
- Should `myteam get role ...` and `myteam get skill ...` print verifier instructions to stdout,
  stderr, or both?
- What is the cleanest packaged built-in role mechanism given today’s built-in-skill-only model?
- Should verification attach only to downloaded subtrees, or also to third-party packaged provider
  content in the future?
