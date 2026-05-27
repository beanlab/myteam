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
    sections.extend(_workflow_command_instructions(session_nonce))
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
    session_nonce: str | None,
    objective_text: str,
    resolved_input: Any,
    output_template: dict[str, Any] | None,
    child_workflow: str,
    child_result: dict[str, Any],
) -> str:
    sections = [
        "Complete the objective below.",
        "",
    ]
    sections.extend(_workflow_command_instructions(session_nonce))
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
            "Original objective:",
            objective_text,
            "",
        ]
    )
    if (err := child_result.get("error_message")) is not None:
        sections.extend([
            f"{child_workflow} result:",
            "Error:",
            f"{err}",
            "",
            json.dumps(child_result, indent=2),
            "",
            "Correct the error and try again"
        ])
    else:
        sections.extend([
            f"Child workflow completed: {child_workflow}",
            json.dumps(child_result, indent=2),
            "",
            "Continue from the point where you requested the child workflow.",
        ])
    return "\n".join(sections)


def _workflow_command_instructions(session_nonce: str | None) -> list[str]:
    if session_nonce is None:
        return []
    return [
        f"Session nonce: {session_nonce}",
        "",
        "Use this nonce with both workflow commands.",
        "If you are asked to launch a workflow, run",
        f"`myteam workflow-start <workflow> --session-nonce {session_nonce}`",
        "and pass required input with `--json`, `--text`, or standard input.",
    ]
