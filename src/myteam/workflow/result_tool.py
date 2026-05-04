from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .terminal.result_channel import submit_result_payload


def workflow_result(json: str | None = None, text: str | None = None) -> None:
    try:
        payload = _read_payload(json_text=json, text=text)
        submit_result_payload(payload)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)

    print("Workflow result accepted.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="myteam workflow-result")
    parser.add_argument("--json")
    parser.add_argument("--text")
    args = parser.parse_args(argv)

    try:
        payload = _read_payload(json_text=args.json, text=args.text)
        submit_result_payload(payload)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print("Workflow result accepted.")
    return 0


def _read_payload(*, json_text: str | None, text: str | None) -> Any:
    if json_text is not None and text is not None:
        raise ValueError("Pass only one of --json or --text.")
    if text is not None:
        return {"text": text}
    if json_text is not None:
        return json.loads(json_text)

    raw = sys.stdin.read().strip()
    if not raw:
        raise ValueError("Expected JSON on stdin, --json, or --text.")
    return json.loads(raw)


if __name__ == "__main__":
    raise SystemExit(main())
