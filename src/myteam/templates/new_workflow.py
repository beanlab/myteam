"""
type: workflow
description: "This workflow has not yet been implemented; if you see this, please inform the user of the error."
usage: no arguments
"""
from __future__ import annotations

import json

from myteam import run_agent


def main() -> None:
    result = run_agent(prompt="Not implemented yet. Tell the user.")
    print(json.dumps(result.output))


if __name__ == "__main__":
    main()
