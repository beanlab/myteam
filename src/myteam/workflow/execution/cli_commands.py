from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable

from ..terminal.control_channel import submit_child_workflow_request
from ..terminal.result_channel import submit_result_payload


def workflow_start(
    workflow: str,
    json: Any | None = None,
    text: str | None = None,
    session_nonce: str | None = None,
) -> None:
    raise SystemExit(
        _run_submission(
            payload_reader=lambda: _read_payload(json_text=json, text=text, allow_empty_stdin=True),
            submitter=lambda payload: submit_child_workflow_request(workflow, payload, session_nonce=session_nonce),
            success_message="Workflow start request accepted.",
        )
    )


def workflow_result(
    json: str | None = None,
    text: str | None = None,
    session_nonce: str | None = None,
) -> None:
    raise SystemExit(
        _run_submission(
            payload_reader=lambda: _read_payload(json_text=json, text=text, allow_empty_stdin=False),
            submitter=lambda payload: submit_result_payload(payload, session_nonce=session_nonce),
            success_message="Workflow result accepted.",
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="myteam workflow")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("start")
    start_parser.add_argument("workflow")
    start_parser.add_argument("--session-nonce", required=True)
    start_parser.add_argument("--json")
    start_parser.add_argument("--text")

    result_parser = subparsers.add_parser("result")
    result_parser.add_argument("--session-nonce", required=True)
    result_parser.add_argument("--json")
    result_parser.add_argument("--text")

    args = parser.parse_args(argv)
    if args.command == "start":
        return _run_submission(
            payload_reader=lambda: _read_payload(
                json_text=args.json,
                text=args.text,
                allow_empty_stdin=True,
            ),
            submitter=lambda payload: submit_child_workflow_request(
                args.workflow,
                payload,
                session_nonce=args.session_nonce,
            ),
            success_message="Workflow start request accepted.",
        )
    return _run_submission(
        payload_reader=lambda: _read_payload(
            json_text=args.json,
            text=args.text,
            allow_empty_stdin=False,
        ),
        submitter=lambda payload: submit_result_payload(payload, session_nonce=args.session_nonce),
        success_message="Workflow result accepted.",
    )


def _run_submission(
    *,
    payload_reader: Callable[[], Any | None],
    submitter: Callable[[Any | None], None],
    success_message: str,
) -> int:
    try:
        payload = payload_reader()
        submitter(payload)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(success_message)
    return 0


def _read_payload(*, json_text: Any | None, text: str | None, allow_empty_stdin: bool) -> Any | None:
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
        if allow_empty_stdin:
            return None
        raise ValueError("Expected JSON on stdin, --json, or --text.")
    return json.loads(raw)
