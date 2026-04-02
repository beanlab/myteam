# Third-Party Skill Tree Provider Design

## Summary

Allow installed third-party Python packages to expose entire `myteam` skill trees through a
provider interface, while keeping `myteam get skill` local-only and deterministic at runtime.

The key design move is to replace the current special-case `builtins/` resolver with a general
"skill provider" registry. Each provider owns one or more top-level skill namespaces and maps them
to a local filesystem tree containing normal `skill.md` and `load.py` nodes.

This preserves the current loading model:

- `myteam get skill ...` still resolves to a local directory
- `load.py` is still the execution boundary
- discovery still comes from the files under the resolved node

What changes is only how the root of a skill path is resolved.

## Problem

Today `myteam` supports two skill sources:

- project-local skills under `.myteam/`
- packaged built-in skills under the reserved `builtins/` namespace

That works because `builtins/` is hard-coded as a second filesystem root. It does not scale to
third parties:

- importing a third-party module inside `load.py` is enough for one skill, but not for a full tree
- nested children need stable path resolution and discovery, not ad hoc delegation code
- multiple packages need conflict handling for namespace ownership
- the application interface currently describes only project-local skills plus `builtins/`

If we solve this by letting arbitrary `load.py` files reach out to package internals dynamically, we
lose the simplicity of "a skill path resolves to a directory tree and then executes `load.py` there."

## Goals

- Support whole third-party skill trees, not just one-off imported skills.
- Keep `myteam get skill` local-only and filesystem-based at runtime.
- Preserve the existing mental model that a skill is a directory with `skill.md` and `load.py`.
- Let third-party packages ship and version their own skill content.
- Allow multiple providers to coexist without ambiguous path resolution.
- Keep the current built-in `builtins/` behavior as one instance of the same mechanism.

## Non-Goals

- Remote fetching during `get skill`.
- Merging project-local and provider-owned content into one mixed directory view.
- Letting two providers contribute children under the same exact namespace.
- Replacing normal on-disk skill trees with an API-only virtual tree.

## Proposed Model

### Skill providers

A skill provider is a local source of `myteam` skill trees. A provider declares:

- provider name
- owning Python package or module
- one or more top-level namespaces it owns
- filesystem root for its skill tree
- optional metadata such as version or provenance text

Each provider root must contain normal `myteam` skill directories below it.

Example:

- built-in provider owns `builtins`
- package `acme_toolkit` owns `acme`
- package `pandas_agent_tools` owns `pandas`

Then:

- `myteam get skill builtins/changelog` resolves into the built-in packaged tree
- `myteam get skill acme/sql/debugging` resolves into the installed `acme_toolkit` tree

### Namespace ownership

Each top-level namespace has exactly one owner.

Resolution order should be:

1. provider-owned namespace if the first path segment matches a registered provider namespace
2. otherwise project-local `.myteam/<path>`

This keeps third-party paths explicit and avoids surprising project overrides of shipped provider
content.

That is the same rule already used for `builtins/`: a reserved namespace resolves away from
`.myteam/`.

### Filesystem requirement

Providers should expose a real directory on local disk, not only Python objects.

That directory is the canonical tree for:

- existence checks
- listing child skills
- reading `skill.md`
- executing `load.py`

This keeps existing utilities, templates, and tests mostly valid.

## Provider Registration

Use Python package entry points rather than import-by-convention from arbitrary `load.py` code.

Proposed entry point group:

- `myteam.skill_providers`

Each entry point returns provider metadata. For example, a package could expose:

- namespaces: `["acme"]`
- root: `/.../site-packages/acme_toolkit/myteam_skills`

The provider object should be intentionally small. It only needs to answer:

- what namespaces do you own?
- where is the local skill-tree root for each namespace?

This is enough for path resolution and keeps provider loading simple.

### Why entry points

Entry points are better than "teach users to import a package from `load.py`" because they:

- scale from one skill to full trees
- allow discovery without custom glue code in project files
- make namespace conflicts detectable before skill execution
- fit installed third-party libraries naturally

## Interface Sketch

The exact Python API can change, but the CLI-facing contract should look like this:

- `commands.get_skill()` asks a resolver for the base directory for a skill path
- the resolver returns `(source_kind, root_dir, logical_path)` or a similar structure
- `commands.get_skill()` joins the path under that root, validates `is_skill_dir`, and executes
  `load.py`

Near-term internal interface:

```python
@dataclass(frozen=True)
class SkillProvider:
    name: str
    namespaces: tuple[str, ...]

    def root_for_namespace(self, namespace: str) -> Path: ...
```

Resolver helpers:

```python
def iter_skill_providers() -> Iterable[SkillProvider]: ...
def resolve_skill_root(skill_path: str) -> tuple[str, Path, str]: ...
def provider_for_namespace(namespace: str) -> SkillProvider | None: ...
```

The built-in tree should be migrated onto this interface instead of remaining a special case.

## Discovery Behavior

Discovery should remain local to the resolved node.

Once a provider-owned path resolves to a real directory, the existing listing functions can operate
normally on that subtree.

At the root role level, `myteam` may also want to expose provider namespaces as discoverable entry
points, similar to how `builtins` is surfaced today. That should be treated as a separate UX
decision from path resolution itself.

Recommended near-term behavior:

- keep root listing of packaged `builtins`
- do not automatically list every installed third-party namespace from the root role yet

Reason: dumping all installed provider namespaces into every project's discovery output may be noisy
and may expose tools the project author never intended to advertise. Third-party resolution can
exist first; root-level discoverability can be added later behind explicit project authoring.

## Conflict Policy

Namespace conflicts must fail clearly.

Cases:

- provider namespace collides with another provider namespace
- provider namespace collides with reserved internal names

Recommended rule:

- `builtins` remains reserved for the packaged built-in provider
- duplicate provider namespace registration raises a deterministic error
- project-local `.myteam/<namespace>` does not override a provider-owned namespace

This is stricter than Python import shadowing, and that is good here because instruction loading
needs predictability.

## Packaging Guidance For Third Parties

A third-party package that wants to ship skills should include a normal directory tree in package
data, for example:

```text
acme_toolkit/
  myteam_skills/
    acme/
      skill.md
      load.py
      sql/
        skill.md
        load.py
```

The provider root for namespace `acme` would be the parent directory containing `acme/`, not the
`acme/` directory itself, so path joining stays uniform with the built-in resolver model.

This gives library authors a low-friction authoring story: they ship ordinary `myteam` skill files.

## Security and Trust Notes

This feature does not create a new execution boundary. `load.py` from installed packages is already
code execution, just as project-local `load.py` is.

However, it does widen the set of local code that may be loaded through `myteam get skill`. That
means:

- provider namespaces should be explicit
- conflict errors should be loud
- future trust/provenance work should include provider packages as another instruction source class

This should stay out of scope for the initial provider implementation, but the design should leave
room for a later `myteam list providers` or trust-reporting command.

## Implementation Plan

### Phase 1: internal resolver cleanup

- Introduce a general skill-provider resolver abstraction.
- Reimplement `builtins/` on top of that abstraction.
- Replace direct `builtins` path branching in `commands.py` and helper code.

### Phase 2: packaged provider loading

- Load third-party providers from Python entry points.
- Validate namespace uniqueness.
- Resolve provider-owned skill paths through the shared resolver.

### Phase 3: user-facing polish

- Document provider-owned namespaces in the README and application interface.
- Decide whether and how provider namespaces appear in discovery listings.
- Consider diagnostics such as listing installed providers and their owned namespaces.

## Code Impact Areas

- `src/myteam/commands.py`
  `get_skill()` should stop hard-coding `builtins`.
- `src/myteam/utils.py`
  builtin-specific helpers should be generalized into provider resolution helpers.
- `src/myteam/paths.py`
  likely keep only built-in path helpers that the built-in provider itself uses.
- tests
  add provider registration and namespace-conflict cases.
- docs
  update README and `application_interface.md` once the design is implemented.

## Open Questions

- Should provider namespaces be discoverable only when a project explicitly opts in?
- Do we want a command to list installed skill providers for debugging?
- Should provider loading ignore broken entry points and continue, or fail fast?
- Should a provider be allowed to expose multiple namespaces, or should we require one provider per
  namespace?
- Should role trees eventually gain the same provider mechanism, or should this remain skill-only?
