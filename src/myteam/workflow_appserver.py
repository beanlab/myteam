"""JSON-RPC client for the workflow AppServer subprocess."""
from __future__ import annotations

import json
import queue
import shlex
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import __version__
from .workflow_definition import WorkflowError


@dataclass
class PendingResponse:
    event: threading.Event = field(default_factory=threading.Event)
    result: Any = None
    error: dict[str, Any] | None = None


class JsonRpcProcessClient:
    def __init__(self, command: str, *, cwd: Path):
        self.command = command
        self.cwd = cwd
        self.process: subprocess.Popen[str] | None = None
        self._request_id = 0
        self._write_lock = threading.Lock()
        self._pending: dict[int, PendingResponse] = {}
        self._pending_lock = threading.Lock()
        self._notifications: queue.Queue[dict[str, Any]] = queue.Queue()
        self._stderr_lines: list[str] = []
        self._stdout_thread: threading.Thread | None = None
        self._stderr_thread: threading.Thread | None = None

    def __enter__(self) -> "JsonRpcProcessClient":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def start(self) -> None:
        args = shlex.split(self.command)
        if not args:
            raise WorkflowError("workflow app server command is empty")
        self.process = subprocess.Popen(
            args,
            cwd=self.cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        assert self.process.stdout is not None
        assert self.process.stderr is not None
        self._stdout_thread = threading.Thread(target=self._read_stdout, daemon=True)
        self._stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
        self._stdout_thread.start()
        self._stderr_thread.start()

    def initialize(self) -> None:
        self.request(
            "initialize",
            {
                "clientInfo": {
                    "name": "myteam",
                    "version": __version__,
                },
                "capabilities": {
                    "experimentalApi": True,
                },
            },
        )

    def close(self) -> None:
        if self.process is None:
            return
        if self.process.stdin and not self.process.stdin.closed:
            self.process.stdin.close()
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
        self.process = None

    def request(self, method: str, params: dict[str, Any], *, timeout: float = 30.0) -> Any:
        if self.process is None or self.process.stdin is None:
            raise WorkflowError("workflow app server process is not running")
        request_id = self._next_request_id()
        pending = PendingResponse()
        with self._pending_lock:
            self._pending[request_id] = pending
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }
        with self._write_lock:
            try:
                self.process.stdin.write(json.dumps(payload))
                self.process.stdin.write("\n")
                self.process.stdin.flush()
            except OSError as exc:
                raise WorkflowError(f"workflow app server is unavailable: {exc}") from exc
        if not pending.event.wait(timeout):
            with self._pending_lock:
                self._pending.pop(request_id, None)
            raise WorkflowError(f"timed out waiting for {method} response")
        if pending.error is not None:
            message = pending.error.get("message", f"{method} failed")
            raise WorkflowError(message)
        return pending.result

    def next_notification(self, *, timeout: float = 0.1) -> dict[str, Any] | None:
        try:
            return self._notifications.get(timeout=timeout)
        except queue.Empty:
            return None

    def _next_request_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _read_stdout(self) -> None:
        assert self.process is not None
        assert self.process.stdout is not None
        for line in self.process.stdout:
            payload = line.strip()
            if not payload:
                continue
            try:
                message = json.loads(payload)
            except json.JSONDecodeError:
                self._stderr_lines.append(f"invalid JSON from workflow server: {payload}")
                continue
            if "id" in message:
                self._handle_response(message)
                continue
            if "method" in message:
                self._notifications.put(message)

    def _read_stderr(self) -> None:
        assert self.process is not None
        assert self.process.stderr is not None
        for line in self.process.stderr:
            self._stderr_lines.append(line.rstrip("\n"))

    def _handle_response(self, message: dict[str, Any]) -> None:
        response_id = message.get("id")
        if not isinstance(response_id, int):
            return
        with self._pending_lock:
            pending = self._pending.pop(response_id, None)
        if pending is None:
            return
        pending.result = message.get("result")
        pending.error = message.get("error")
        pending.event.set()
