"""
type: workflow
description: "A demo workflow showing how to use session resuming"
usage: no arguments
"""
from __future__ import annotations

import json

from myteam import report_workflow_result, run_agent


def main() -> None:
    result = run_agent(
        prompt="Write two poems about trees. Both haiku."
    )
    
    # User calls /quit to end the session
    
    run_agent(
        prompt="Tell me which poem you like more.",
        session_id=result.session_id
    )

    report_workflow_result(None)


if __name__ == "__main__":
    main()
