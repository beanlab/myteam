"""Private implementation of the ``myteam where`` CLI command."""
from __future__ import annotations

import os
from pathlib import Path
import sys
import unicodedata
from typing import Any

from .execution.protocol import ENV_SOCKET, KIND_GET_STACK, RpcClient


def where_cli():
    socket_path = os.environ.get(ENV_SOCKET)
    if not socket_path:
        print("myteam where must run inside a process managed by myteam start.", file=sys.stderr)
        raise SystemExit(1)
    try:
        response = RpcClient(socket_path).call(KIND_GET_STACK)
        entries = _validate_snapshot(response)
        text = format_stack(entries)
    except Exception as exc:
        print("Unable to retrieve complete myteam workflow stack.", file=sys.stderr)
        raise SystemExit(1) from exc
    print(text, end="")


def _validate_snapshot(response: dict[str, Any]) -> list[dict[str, Any]]:
    if response.get("complete") is not True:
        raise ValueError("supervisor returned an incomplete stack")
    entries = response.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("supervisor returned invalid stack entries")
    validated: list[dict[str, Any]] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or entry.get("depth") != index:
            raise ValueError("supervisor returned an invalid stack hierarchy")
        kind = entry.get("type")
        if kind == "workflow":
            path = entry.get("workflow_path")
            if not isinstance(path, str) or not Path(path).is_absolute() or str(Path(path).resolve()) != path:
                raise ValueError("supervisor returned an invalid workflow path")
            validated.append({"type": kind, "depth": index, "workflow_path": path})
            continue
        if kind == "agent":
            name = entry.get("name")
            agent = entry.get("agent")
            model = entry.get("model")
            session_id = entry.get("session_id")
            if not isinstance(name, str) or not isinstance(agent, str) or not agent:
                raise ValueError("supervisor returned invalid agent metadata")
            if model is not None and not isinstance(model, str):
                raise ValueError("supervisor returned invalid agent model")
            if session_id is not None and not isinstance(session_id, str):
                raise ValueError("supervisor returned invalid native session ID")
            item = {"type": kind, "depth": index, "name": name, "agent": agent}
            if model is not None:
                item["model"] = model
            if session_id is not None:
                item["session_id"] = session_id
            validated.append(item)
            continue
        raise ValueError("supervisor returned an unknown stack entry type")
    return validated


def format_stack(entries: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for entry in entries:
        prefix = "  " * entry["depth"]
        if entry["type"] == "workflow":
            value = _escape_controls(entry["workflow_path"])
        else:
            fields = [f"agent={_escape_controls(entry['agent'])}"]
            if "model" in entry:
                fields.append(f"model={_escape_controls(entry['model'])}")
            if "session_id" in entry:
                fields.append(f"session_id={_escape_controls(entry['session_id'])}")
            value = f"{_escape_controls(entry['name'])} ({', '.join(fields)})"
        lines.append(prefix + value)
    return "".join(f"{line}\n" for line in lines)


def _escape_controls(value: str) -> str:
    escaped: list[str] = []
    named = {"\n": r"\n", "\r": r"\r", "\t": r"\t"}
    for character in value:
        if not unicodedata.category(character).startswith("C"):
            escaped.append(character)
        elif character in named:
            escaped.append(named[character])
        else:
            codepoint = ord(character)
            if codepoint <= 0xFF:
                escaped.append(f"\\x{codepoint:02x}")
            elif codepoint <= 0xFFFF:
                escaped.append(f"\\u{codepoint:04x}")
            else:
                escaped.append(f"\\U{codepoint:08x}")
    return "".join(escaped)
