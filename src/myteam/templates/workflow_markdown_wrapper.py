from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from myteam.config import load_myteam_config
from myteam.frontmatter import split_markdown_frontmatter
from myteam.workflows import report_workflow_result, run_agent
from myteam.workflows.commands import resolve_agent_settings


def main(
    markdown_file: Path,
    workflow_inputs: str = "{}",
    workflow_target: str | None = None,
) -> None:
    input_values = _load_json_object(workflow_inputs)
    frontmatter, content = split_markdown_frontmatter(markdown_file.read_text(encoding="utf-8"))
    config = load_myteam_config(Path.cwd())
    settings = resolve_agent_settings(frontmatter, config.defaults if config is not None else None)
    if "session_name" not in settings:
        settings["session_name"] = workflow_target if workflow_target is not None else str(markdown_file)
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
    )
