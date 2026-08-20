# Package governing documents with `myteam`

## Problem

A wheel built from the current project does not contain `src/governing_docs`. The installed `myteam.commands.GOVERNING_DOCS_ROOT` points to a sibling `governing_docs` directory in `site-packages`, but that directory is absent. As a result, `myteam onboard` from an installed wheel exits with:

```text
Not a governing docs folder: .../site-packages/governing_docs
```

This also means governing-document updates are not delivered through the packaged onboarding command.

## Findings

- The failure was reproduced by building a fresh 0.3.8 wheel, extracting it outside the repository, and calling `onboard()`.
- The wheel contains `myteam/**` but no `governing_docs/**`.
- `src/myteam/commands.py` intentionally resolves the default docs root as `Path(__file__).resolve().parents[1] / "governing_docs"`.
- The project uses `uv_build`, whose default wheel discovery includes the `myteam` module only.
- `uv_build` supports explicitly packaging multiple root modules through `tool.uv.build-backend.module-name`.

## Proposal

Preserve the existing `src/governing_docs` location and runtime lookup rather than moving or duplicating the documents:

1. Make `src/governing_docs` an installable package/module, likely with a minimal `__init__.py`.
2. Configure `uv_build` with explicit module names for both `myteam` and `governing_docs`.
3. Build both wheel and sdist and verify every governing Markdown document is included at the expected installed path.
4. Add an artifact-level regression test that installs or extracts the built wheel outside the source tree and confirms `myteam onboard` succeeds and includes representative governing documents.

This should be a focused packaging correction. The main risk is a source-tree test passing while the built artifact remains incomplete, so validation must exercise the wheel rather than only the editable development environment.
