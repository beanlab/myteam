from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from myteam.frontmatter import split_markdown_frontmatter
from myteam.workflows import report_workflow_result, run_agent
from myteam.workflows.commands import resolve_agent_settings


def main(markdown_file: Path, workflow_inputs: str = "{}") -> None:
    input_values = _load_json_object(workflow_inputs)
    frontmatter, content = split_markdown_frontmatter(markdown_file.read_text(encoding="utf-8"))

    settings = resolve_agent_settings(frontmatter)
    output_schema = frontmatter.get("output")

    result = run_agent(
        prompt=content,
        input=input_values,
        output=output_schema if isinstance(output_schema, dict) else None,
        **settings,
    )
    if result.output is not None:
        report_workflow_result(json.dumps(result.output) + "\n")
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
    main(Path(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else "{}")
