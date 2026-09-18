"""
type: workflow
description: Develop an MDXCanvas feature from discovery through release.
usage: no arguments
"""
from pathlib import Path

from rosters.dev.feature_flow.feature_flow import main

PROJECT_ROOT = Path(__file__).resolve().parents[3]

if __name__ == "__main__":
    main(PROJECT_ROOT / ".agents/project.md")
