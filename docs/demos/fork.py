"""
type: workflow
description: "Demo workflow showing how to use fork and resume"
usage: no arguments
"""
from __future__ import annotations

import json
from pathlib import Path

from myteam import report_workflow_result, run_agent


def main():
    result = run_agent(
        prompt="Describe two possible ways to implement a stateless email client "
    )
    
    report_workflow_result(None)


if __name__ == "__main__":
    main()
