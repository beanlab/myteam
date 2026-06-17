"""
type: workflow
description: "A workflow for identifying the source of a bug and fixing it"
usage: no arguments
"""
from __future__ import annotations

import json
from typing import Any

from myteam import report_workflow_result, run_agent


def _run_intake_step() -> dict[str, Any]:
    prompt = (
        "You are the intake step of a bug-fix workflow. "
        "Discuss with the user the symptoms of the bug; "
        "interview them to get a complete understanding of all they know about the issue. "
        "Capture the user's own description of the problem and do not investigate or solve it yet."
    )
    output_schema = {
        "problem_description": "all details about the bug, including expected and observed behaviors",
        "reproduction_conditions": "specific instructions from the user for how to reproduce the bug, if they know them",
        "suspected_area": "where the user suspects the bug may be",
        "open_questions": ["only include questions the user could not answer, but may still matter for fixing the bug"],
    }
    result = run_agent(prompt=prompt, output=output_schema)
    return result.output


def _run_root_cause_step(intake: dict[str, Any]) -> dict[str, Any]:
    prompt = (
        "You are the root-cause analysis step of a bug-fix workflow. "
        "Use the completed intake notes below, inspect the repository, and identify the most likely source of the bug. "
        "Explain why the code fails, name the relevant files and symbols, and record any alternative hypotheses.\n\n"
        f"Problem description:\n{intake['problem_description']}\n\n"
        f"Reproduction conditions:\n{intake['reproduction_conditions']}\n\n"
        f"User's suspected area:\n{intake['suspected_area']}\n\n"
        f"Open questions:\n{json.dumps(intake['open_questions'], indent=2, sort_keys=True)}"
    )
    output_schema = {
        "root_cause_summary": "concise explanation of the underlying bug source and failure mechanism",
        "faulty_files": ["the files most likely responsible for the bug or needing changes"],
        "faulty_symbols": ["the functions, classes, or modules implicated in the failure"],
        "why_it_fails": "a step-by-step explanation of how the bug occurs",
        "confidence": "low, medium, or high confidence in the diagnosis",
        "alternative_hypotheses": ["other plausible explanations that were considered"],
    }
    result = run_agent(prompt=prompt, output=output_schema)
    return result.output


def _run_reproduction_step(
        intake: dict[str, Any],
        root_cause: dict[str, Any],
) -> dict[str, Any]:
    prompt = (
        "You are the reproduction step of a bug-fix workflow. "
        "Create or identify the smallest reliable reproduction for the bug. "
        "Prefer a failing test if the project has a test suite. "
        "Show the commands or steps needed to reproduce the problem, and summarize the evidence.\n\n"
        f"Problem description:\n{intake['problem_description']}\n\n"
        f"Root cause summary:\n{root_cause['root_cause_summary']}\n\n"
        f"Why it fails:\n{root_cause['why_it_fails']}\n\n"
        f"Likely faulty files:\n{json.dumps(root_cause['faulty_files'], indent=2, sort_keys=True)}"
    )
    output_schema = {
        "repro_exists": "whether a reliable reproduction was found or created",
        "repro_type": "the reproduction format, such as test, script, manual, or unknown",
        "repro_location": "where the reproduction lives, if applicable",
        "repro_steps": ["the exact steps or commands required to reproduce the bug"],
        "failing_test_command": "the command that demonstrates the failure, if a test exists",
        "failure_summary": "a concise summary of the observed failure",
        "evidence": ["supporting observations that prove the bug is reproducible"],
    }
    result = run_agent(prompt=prompt, output=output_schema)
    return result.output


def _run_fix_step(
        intake: dict[str, Any],
        root_cause: dict[str, Any],
        reproduction: dict[str, Any],
) -> dict[str, Any]:
    prompt = (
        "You are the implementation step of a bug-fix workflow. "
        "Apply the smallest safe code change that fixes the bug. "
        "Use the intake notes, root-cause analysis, and reproduction evidence below. "
        "Edit the code in the repository as needed, but do not write a final user-facing report yet.\n\n"
        f"Problem description:\n{intake['problem_description']}\n\n"
        f"Root cause summary:\n{root_cause['root_cause_summary']}\n\n"
        f"Reproduction failure summary:\n{reproduction['failure_summary']}\n\n"
        f"Reproduction steps:\n{json.dumps(reproduction['repro_steps'], indent=2, sort_keys=True)}"
    )
    output_schema = {
        "files_changed": ["the files modified to implement the fix"],
        "changes_summary": "a concise summary of the code changes that were made",
        "fix_strategy": "the approach used to correct the bug",
        "behavioral_effect": "how the program behaves differently after the fix",
        "risk_notes": ["important risks, tradeoffs, or follow-up concerns"],
    }
    result = run_agent(prompt=prompt, output=output_schema)
    return result.output


def _run_verification_step(
        intake: dict[str, Any],
        root_cause: dict[str, Any],
        reproduction: dict[str, Any],
        fix: dict[str, Any],
) -> dict[str, Any]:
    prompt = (
        "You are the verification step of a bug-fix workflow. "
        "Run the most relevant tests or checks to confirm the bug is fixed and to detect regressions. "
        "Summarize what you ran, whether the bug is fixed, and any remaining concerns.\n\n"
        f"Problem description:\n{intake['problem_description']}\n\n"
        f"Root cause summary:\n{root_cause['root_cause_summary']}\n\n"
        f"Reproduction failure summary:\n{reproduction['failure_summary']}\n\n"
        f"Fix summary:\n{fix['changes_summary']}"
    )
    output_schema = {
        "tests_run": ["the commands or checks that were run to verify the fix"],
        "test_results": [
            {
                "command": "the verification command that was executed",
                "passed": "whether that command succeeded",
                "notes": "what the command showed or why it matters",
            }
        ],
        "bug_fixed": "whether the bug is now fixed",
        "regressions_found": "whether any regressions or new issues were discovered",
        "remaining_issues": ["any unresolved concerns or follow-up items"],
    }
    result = run_agent(prompt=prompt, output=output_schema)
    return result.output


def _report_final_result(
        intake: dict[str, Any],
        root_cause: dict[str, Any],
        reproduction: dict[str, Any],
        fix: dict[str, Any],
        verification: dict[str, Any],
) -> None:
    lines: list[str] = [
        "Bug fix workflow complete.",
        f"Problem: {intake['problem_description']}",
        f"Root cause: {root_cause['root_cause_summary']}",
        f"Reproduction: {reproduction['failure_summary']}",
        f"Fix: {fix['changes_summary']}"
    ]

    if verification["bug_fixed"] is True:
        lines.append("Verification: bug fixed.")
        
    elif verification["bug_fixed"] is False:
        lines.append("Verification: bug not yet fully fixed.")

    remaining_issues = verification["remaining_issues"]
    if remaining_issues:
        lines.append("Remaining issues:")
        for issue in remaining_issues:
            lines.append(f"- {issue}")

    report_workflow_result("\n".join(lines) + "\n")


def main() -> None:
    intake = _run_intake_step()
    root_cause = _run_root_cause_step(intake)
    reproduction = _run_reproduction_step(intake, root_cause)
    fix = _run_fix_step(intake, root_cause, reproduction)
    verification = _run_verification_step(intake, root_cause, reproduction, fix)
    _report_final_result(intake, root_cause, reproduction, fix, verification)


if __name__ == "__main__":
    main()
