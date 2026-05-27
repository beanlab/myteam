from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .terminal.control_channel import submit_child_workflow_request


def workflow_start(
    workflow: str,
    json: Any | None = None,
    text: str | None = None,
    session_nonce: str | None = None,
) -> None:
    raise SystemExit(_run_submission(workflow=workflow, json_text=json, text=text, session_nonce=session_nonce))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="myteam workflow-start")
    parser.add_argument("workflow")
    parser.add_argument("--session-nonce", required=True)
    parser.add_argument("--json")
    parser.add_argument("--text")
    args = parser.parse_args(argv)
    return _run_submission(
        workflow=args.workflow,
        json_text=args.json,
        text=args.text,
        session_nonce=args.session_nonce,
    )


def _run_submission(*, workflow: str, json_text: Any | None, text: str | None, session_nonce: str | None) -> int:
    try:
        payload = _read_payload(json_text=json_text, text=text)
        submit_child_workflow_request(workflow, payload, session_nonce=session_nonce)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print("Workflow start request accepted.")
    return 0


def _read_payload(*, json_text: Any | None, text: str | None) -> Any | None:
    if json_text is not None and text is not None:
        raise ValueError("Pass only one of --json or --text.")
    if text is not None:
        return {"text": text}
    if json_text is not None:
        if not isinstance(json_text, (str, bytes, bytearray)):
            return json_text
        return json.loads(json_text)

    raw = sys.stdin.read().strip()
    if not raw:
        return None
    return json.loads(raw)


if __name__ == "__main__":
    raise SystemExit(main())
