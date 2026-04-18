from __future__ import annotations

import pytest

from myteam.workflow.reference_resolver import resolve_references


def test_resolve_references_substitutes_exact_string_references_recursively():
    prior_steps = {
        "draft": {
            "prompt": "write a draft",
            "agent": "codex",
            "output": {
                "title": "A Good Title",
                "sections": {
                    "summary": "Short summary",
                },
            },
        },
    }

    resolved = resolve_references(
        {
            "draft_title": "$draft.output.title",
            "payload": {
                "summary": "$draft.output.sections.summary",
                "whole_step": "$draft",
            },
            "items": ["$draft.output", "keep me"],
        },
        prior_steps,
    )

    assert resolved == {
        "draft_title": "A Good Title",
        "payload": {
            "summary": "Short summary",
            "whole_step": prior_steps["draft"],
        },
        "items": [
            {
                "title": "A Good Title",
                "sections": {
                    "summary": "Short summary",
                },
            },
            "keep me",
        ],
    }


def test_resolve_references_leaves_non_reference_strings_unchanged():
    prior_steps = {
        "draft": {
            "output": {
                "title": "A Good Title",
            },
        },
    }

    resolved = resolve_references(
        {
            "message": "prefix $draft.output.title suffix",
            "literal": "$$draft.output.title",
        },
        prior_steps,
    )

    assert resolved == {
        "message": "prefix $draft.output.title suffix",
        "literal": "$draft.output.title",
    }


def test_resolve_references_rejects_unknown_steps():
    with pytest.raises(ValueError, match="unknown step: missing"):
        resolve_references("$missing.output", {})


def test_resolve_references_rejects_missing_path_segments():
    prior_steps = {
        "draft": {
            "output": {
                "title": "A Good Title",
            },
        },
    }

    with pytest.raises(ValueError, match="path not found"):
        resolve_references("$draft.output.summary", prior_steps)


def test_resolve_references_rejects_list_traversal():
    prior_steps = {
        "draft": {
            "output": {
                "items": ["one", "two"],
            },
        },
    }

    with pytest.raises(ValueError, match="do not support list traversal"):
        resolve_references("$draft.output.items.0", prior_steps)
