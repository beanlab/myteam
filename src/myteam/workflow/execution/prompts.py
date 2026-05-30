from __future__ import annotations

import json
from typing import Any

from ...disclosure import format_named_info_block


def build_step_prompt(
    *,
    resolved_input: Any,
    objective_text: str,
    output_template: dict[str, Any] | None,
    session_nonce: str | None,
    skills: list[tuple[str, str]] | None = None,
    tasks: list[tuple[str, str]] | None = None,
) -> str:
    sections = [
        "Complete the objective below.",
        "",
    ]
    if session_nonce is not None:
        sections.extend(
            [
                f"Session nonce: {session_nonce}",
                "",
                "Use this nonce with both workflow commands.",
                "",
                "If you are asked to launch a workflow, use this command:",
                f"`myteam workflow-start <workflow> --session-nonce {session_nonce}`",
                "and pass any required input with `--json` as needed. Use JSON-safe quoting.",
                "",
                "Otherwise, perform the task yourself."
            ]
        )
    if output_template:
        sections.extend([
            "",
            "When you are ready to finish, use this command:",
            f"`myteam workflow-result --session-nonce {session_nonce} --json '{json.dumps(output_template)}'`",
        ])
    if skills:
        sections.extend(["", format_named_info_block("Skills", skills)])
    if tasks:
        sections.extend(["", format_named_info_block("Tasks", tasks)])
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
    skills: list[tuple[str, str]] | None = None,
    tasks: list[tuple[str, str]] | None = None,
) -> str:
    sections = ["Continue with the existing objective.", ""]
    if skills:
        sections.extend([format_named_info_block("Skills", skills), ""])
    if tasks:
        sections.extend([format_named_info_block("Tasks", tasks), ""])
    sections.append(f"{child_workflow} result:")
    if (err := child_result.get("error_message")) is not None:
        sections.extend([
            "Error:",
            f"{err}",
            "",
            "Correct the error and try again with updated input if needed.",
        ])
    else:
        sections.extend([
            json.dumps(child_result, indent=2),
            "",
            "Continue your objective or summarize the result for the user if there",
            "is no clear next step. Do not call workflow-result unless your objective",
            "has been met.",
        ])
    return "\n".join(sections)
