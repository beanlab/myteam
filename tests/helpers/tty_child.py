from __future__ import annotations

import os
import signal
import select
import sys
import termios
import time
import tty


RIGHT_ARROW = "\x1b[C"


def _mode_require_submit_sequence() -> int:
    fd = sys.stdin.fileno()
    original_attrs = termios.tcgetattr(fd)
    received = bytearray()

    try:
        tty.setraw(fd)
        print("READY", flush=True)
        while True:
            ready, _, _ = select.select([fd], [], [], 1.0)
            if not ready:
                print("NO_SUBMIT", flush=True)
                return 4

            chunk = os.read(fd, 1)
            if not chunk:
                print("INPUT_CLOSED", flush=True)
                return 5

            if chunk == b"\n":
                print("LINEFEED_NOT_SUBMIT", flush=True)
                return 6
            if chunk == b"\r":
                if not received.endswith(b"\x1b[C"):
                    print(f"MISSING_RIGHT_ARROW:{received!r}", flush=True)
                    return 7
                payload = received[:-3]
                if not payload:
                    print("MISSING_PAYLOAD", flush=True)
                    return 8
                print(f"RAW_ECHO:{payload.decode('utf-8', errors='replace')}", flush=True)
                print("RIGHT_ARROW_SUBMIT", flush=True)
                return 0

            received.extend(chunk)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, original_attrs)


def _mode_wait_for_quit() -> int:
    print("dog", flush=True)
    for line in sys.stdin:
        command = line.replace(RIGHT_ARROW, "").rstrip("\r\n")
        print(f"INPUT:{command}", flush=True)
        if command == "/quit":
            print("QUIT_ACK", flush=True)
            return 0
    return 1


def _mode_trailing_after_quit() -> int:
    print("dog", flush=True)
    for line in sys.stdin:
        command = line.replace(RIGHT_ARROW, "").rstrip("\r\n")
        if command == "/quit":
            print("QUIT_ACK", flush=True)
            print("TRAILING_OUTPUT", flush=True)
            return 0
    return 1


def _mode_exit_code(code_text: str) -> int:
    print("EXITING", flush=True)
    return int(code_text)


def _mode_silent() -> int:
    signal.signal(signal.SIGTERM, lambda _signum, _frame: sys.exit(0))
    time.sleep(5)
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: tty_child.py <mode> [args...]", file=sys.stderr)
        return 2

    mode = argv[1]
    if mode == "require_submit_sequence":
        return _mode_require_submit_sequence()
    if mode == "wait_for_quit":
        return _mode_wait_for_quit()
    if mode == "trailing_after_quit":
        return _mode_trailing_after_quit()
    if mode == "exit_code":
        return _mode_exit_code(argv[2])
    if mode == "silent":
        return _mode_silent()

    print(f"unknown mode: {mode}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
