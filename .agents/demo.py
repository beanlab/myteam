"""
type: workflow
description: "Writes two poems and picks the best."
usage: no arguments
"""
from __future__ import annotations

import json
from textwrap import dedent

from myteam import report_workflow_result, run_agent


def main() -> None:
    output_schema = {
        "haiku": "A haiku about climbing mountains with small children."
    }

    result1 = run_agent(prompt="Write a poem.", output=output_schema)
    result2 = run_agent(prompt="Write a poem.", output=output_schema)
    result3 = run_agent(
        prompt=dedent("""
            Pick which of these is better.
            {{ poem1 }}
            
            {{ poem2 }}
        """),
        input={'poem1': result1.output['haiku'], 'poem2': result2.output['haiku']},
        output={'reasoning': 'why you picked this poem', 'best_poem': 'the text of the chosen poem'}
    )
    report_workflow_result(result3.output['best_poem'])
    report_workflow_result(result3.output['reasoning'])


if __name__ == "__main__":
    main()
