from __future__ import annotations

import json
from typing import Any


def build_step_prompt(
    *,
    resolved_input: Any,
    objective_text: str,
    output_template: dict[str, Any] | None,
    session_nonce: str | None,
) -> str:
    sections = [
        "Complete the objective below.",
        "",
    ]
    if session_nonce is not None:
        sections.extend(
            [
                f"Session nonce: {session_nonce}",
                "Use this nonce with both workflow commands.",
                "If you need to launch a child workflow, call "
                "`myteam workflow-start <workflow> --session-nonce "
                f"{session_nonce}` and pass the child input with "
                f"`--json`, `--text`, or standard input.",
            ]
        )
    if output_template:
        sections.extend([
            "Return the final workflow result by calling this command:",
            "Replace the placeholder values below with the real final result content.",
            "",
            f"myteam workflow-result --session-nonce {session_nonce} <<'JSON'",
            json.dumps(output_template, indent=2),
            "JSON",
            "",
            "Do not print result markers in the terminal.",
        ])
    if resolved_input is not None:
        sections.extend(
            [
                "",
                "Input:",
                json.dumps(resolved_input, indent=2),
            ]
        )
    sections.extend(
        [
            "",
            "Objective:",
            objective_text,
        ]
    )
    return "\n".join(sections)


def build_child_resume_prompt(
    *,
    child_workflow: str,
    child_result: dict[str, Any],
    original_objective: str,
    output_template: dict[str, Any] | None,
) -> str:
    sections = [
        f"Child workflow completed: {child_workflow}",
        "",
        "Child workflow result:",
        json.dumps(child_result, indent=2),
        "",
        "Continue from the point where you requested the child workflow.",
    ]
    if output_template:
        sections.extend(
            [
                "",
                "Return the final workflow result by calling this command:",
                "Replace the placeholder values below with the real final parent result content.",
                "",
                "myteam workflow-result <<'JSON'",
                json.dumps(output_template, indent=2),
                "JSON",
                "",
                "Do not print result markers in the terminal.",
            ]
        )
    sections.extend(
        [
            "",
            "Original objective:",
            original_objective,
        ]
    )
    return "\n".join(sections)
