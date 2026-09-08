from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from myteam.config import AGENT_SETTING_FIELDS, AgentSettingsModel, load_myteam_config
from myteam.frontmatter import split_markdown_frontmatter
from myteam.workflows import report_workflow_result, run_agent

HELP_TEXT = """Usage: myteam start <markdown-workflow> [--input JSON] [options]

Markdown workflow options (values use YAML syntax):
  --agent VALUE
  --session-name VALUE, --session_name VALUE
  --model VALUE
  --reasoning VALUE
  --interactive VALUE
  --extra-args VALUE, --extra_args VALUE
  --session-id VALUE, --session_id VALUE
  --fork VALUE
  --help

Options accept both `--option VALUE` and `--option=VALUE`. Quote YAML values as
needed for your shell; booleans, lists, and null retain their YAML types.
Repeated options use the last value. Settings resolve from frontmatter, then CLI
overrides, then effective home/project defaults for null or missing values. A
missing session name finally falls back to the workflow path. `fork: true`
requires an effective session ID. `--input` supplies the workflow's JSON object.
"""

_OPTION_FIELDS = {
    "--agent": "agent",
    "--session-name": "session_name",
    "--session_name": "session_name",
    "--model": "model",
    "--reasoning": "reasoning",
    "--interactive": "interactive",
    "--extra-args": "extra_args",
    "--extra_args": "extra_args",
    "--session-id": "session_id",
    "--session_id": "session_id",
    "--fork": "fork",
}


def main(
    markdown_file: Path,
    workflow_inputs: str = "{}",
    workflow_target: str | None = None,
    *workflow_args: str,
) -> None:
    if "--help" in workflow_args:
        report_workflow_result(HELP_TEXT, end="")
        return

    try:
        overrides = _parse_overrides(workflow_args)
        input_values = _load_json_object(workflow_inputs)
        frontmatter, content = split_markdown_frontmatter(markdown_file.read_text(encoding="utf-8"))
        config = load_myteam_config(Path.cwd())
        settings = _resolve_settings(
            frontmatter,
            overrides,
            config.defaults if config is not None else None,
            workflow_target if workflow_target is not None else str(markdown_file),
        )
    except (ValueError, UnicodeError) as exc:
        report_workflow_result(_format_error(exc))
        raise SystemExit(1) from None

    output_schema = frontmatter.get("output")
    result = run_agent(
        prompt=content,
        input=input_values,
        prompt_source_path=markdown_file,
        output=output_schema if isinstance(output_schema, dict) else None,
        **settings,
    )
    if result.output is not None:
        report_workflow_result(json.dumps(result.output))
    else:
        report_workflow_result(None)


def _parse_overrides(args: tuple[str, ...]) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    index = 0
    while index < len(args):
        token = args[index]
        if not token.startswith("--"):
            raise ValueError(f"Unexpected positional argument: {token}")

        option, separator, raw_value = token.partition("=")
        field = _OPTION_FIELDS.get(option)
        if field is None:
            raise ValueError(f"Unknown Markdown workflow option: {option}")

        if not separator:
            index += 1
            if index >= len(args) or args[index].startswith("--"):
                raise ValueError(f"Missing value for {option}")
            raw_value = args[index]

        if not raw_value.strip():
            raise ValueError(f"Missing value for {option}")

        try:
            overrides[field] = yaml.safe_load(raw_value)
        except yaml.YAMLError:
            raise ValueError(f"Invalid YAML value for {option}") from None
        index += 1
    return overrides


def _resolve_settings(
    frontmatter: dict[str, Any],
    overrides: dict[str, Any],
    defaults: AgentSettingsModel | dict[str, Any] | None,
    fallback_session_name: str,
) -> dict[str, Any]:
    values = {field: frontmatter[field] for field in AGENT_SETTING_FIELDS if field in frontmatter}
    values.update(overrides)

    for field in AGENT_SETTING_FIELDS:
        if values.get(field) is None and defaults is not None:
            values[field] = defaults.get(field) if isinstance(defaults, dict) else getattr(defaults, field)

    values = {field: value for field, value in values.items() if value is not None}
    if "session_name" not in values:
        values["session_name"] = fallback_session_name

    settings = AgentSettingsModel.model_validate(values).model_dump(exclude_none=True)
    if settings.get("fork") is True and not settings.get("session_id"):
        raise ValueError("fork=true requires an effective session_id")
    return settings


def _format_error(exc: Exception) -> str:
    validation_error: ValidationError | None = None
    current: BaseException | None = exc
    while current is not None:
        if isinstance(current, ValidationError):
            validation_error = current
            break
        current = current.__cause__

    if validation_error is not None:
        detail = validation_error.errors()[0]
        field = ".".join(str(part) for part in detail["loc"])
        return f"Invalid Markdown workflow setting {field!r}: {detail['msg']}."

    message = str(exc).splitlines()[0].rstrip(".")
    return f"Invalid Markdown workflow invocation: {message}."


def _load_json_object(value: str) -> dict[str, Any]:
    if not value.strip():
        return {}
    loaded = json.loads(value)
    if not isinstance(loaded, dict):
        raise ValueError("Workflow input must be a JSON object.")
    return loaded


if __name__ == "__main__":
    main(
        Path(sys.argv[1]),
        sys.argv[2] if len(sys.argv) > 2 else "{}",
        sys.argv[3] if len(sys.argv) > 3 else sys.argv[1],
        *sys.argv[4:],
    )
