"""Small JSON-over-Unix-socket protocol for the session prototype."""
from __future__ import annotations

from dataclasses import dataclass
import json
import socket
from pathlib import Path
from typing import Any

VERSION = 1

ENV_SOCKET = "MYTEAM_MOTHERSHIP_SOCKET"
ENV_SESSION_ID = "MYTEAM_SESSION_ID"
ENV_REQUEST_ID = "MYTEAM_REQUEST_ID"
ENV_SESSION_NONCE = "MYTEAM_SESSION_NONCE"
ENV_WORKFLOW_INVOCATION_ID = "MYTEAM_WORKFLOW_INVOCATION_ID"
ENV_WORKFLOW_INPUT_JSON = "MYTEAM_WORKFLOW_INPUT_JSON"
ENV_AGENT_PROMPT = "MYTEAM_AGENT_PROMPT"
ENV_AGENT_INPUT_JSON = "MYTEAM_AGENT_INPUT_JSON"
ENV_AGENT_OUTPUT_JSON = "MYTEAM_AGENT_OUTPUT_JSON"

KIND_START_WORKFLOW = "start_workflow"
KIND_START_AGENT_SESSION = "start_agent_session"
KIND_REPORT_RESULT = "report_result"
KIND_POLL_RESULT = "poll_result"
KIND_ACK_RESULT = "ack_result"


@dataclass(frozen=True)
class RpcClient:
    """Synchronous one-request-per-connection RPC client."""

    socket_path: str

    def call(self, kind: str, **payload: Any) -> dict[str, Any]:
        message = {"version": VERSION, "kind": kind, **payload}
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.connect(self.socket_path)
            connection.sendall(json.dumps(message).encode("utf-8"))
            connection.shutdown(socket.SHUT_WR)
            raw = read_all(connection)

        try:
            response = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Mothership returned an invalid JSON response.") from exc

        if not isinstance(response, dict):
            raise RuntimeError("Mothership returned a non-object JSON response.")
        if not response.get("ok"):
            raise RuntimeError(str(response.get("error") or "Mothership request failed."))
        return response


def read_all(connection: socket.socket) -> bytes:
    chunks: list[bytes] = []
    while True:
        chunk = connection.recv(65536)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def load_json_object(raw: bytes) -> dict[str, Any]:
    try:
        message = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid JSON payload.") from exc
    if not isinstance(message, dict):
        raise ValueError("RPC payload must be a JSON object.")
    if message.get("version") != VERSION:
        raise ValueError("Unsupported RPC protocol version.")
    return message


def json_response(**payload: Any) -> bytes:
    return json.dumps(payload).encode("utf-8")


def safe_unlink(path: str) -> None:
    try:
        Path(path).unlink()
    except FileNotFoundError:
        pass
