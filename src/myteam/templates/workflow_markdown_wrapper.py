from __future__ import annotations

import json
import sys
from pathlib import Path

from myteam.frontmatter import split_markdown_frontmatter
from myteam.prefix import get_myteam_root
from myteam.tasks import AgentContext
from myteam.workflows.commands import resolve_agent_settings
from myteam.workflows.config import load_workflow_defaults


def main(
        markdown_file: Path,
        workflow_inputs: str
):
    workflow_defaults = load_workflow_defaults(get_myteam_root())
    usage_logging = workflow_defaults.usage_logging if workflow_defaults is not None else None
    timeout = workflow_defaults.timeout if workflow_defaults is not None else None

    winputs = json.loads(workflow_inputs)
    frontmatter, content = split_markdown_frontmatter(markdown_file.read_text())
    # TODO - ensure provided workflow inputs matches schema in frontmatter
    frontmatter.pop('input')

    with AgentContext(
            usage_logging=usage_logging, timeout=timeout
    ) as ctx:
        args = resolve_agent_settings(frontmatter, workflow_defaults)

        args['prompt'] = content.format(**winputs)

        result = ctx.run_agent(**args)

        print(json.dumps(result.output, indent=2))


if __name__ == '__main__':
    main(Path(sys.argv[1]), sys.argv[2])
