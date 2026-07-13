"""
type: workflow
description: "This workflow has not yet been implemented; if you see this, please inform the user of the error."
usage: no arguments
"""
from __future__ import annotations

import json

from myteam import report_workflow_result, run_agent


def main() -> None:
    result = run_agent(prompt="Not implemented yet. Tell the user.")
    if result.output is not None:
        report_workflow_result(json.dumps(result.output))
    else:
        report_workflow_result(None)


if __name__ == "__main__":
    main()
