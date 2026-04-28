from __future__ import annotations

import os
import select
import signal
import sys
import time


def _mode_echo_initial() -> int:
    print("READY", flush=True)
    line = sys.stdin.readline()
    print(f"ECHO:{line.rstrip()}", flush=True)
    return 0


def _mode_wait_for_quit() -> int:
    print("dog", flush=True)
    for line in sys.stdin:
        command = line.rstrip("\r\n")
        print(f"INPUT:{command}", flush=True)
        if command == "/quit":
            print("QUIT_ACK", flush=True)
            return 0
    return 1


def _mode_trailing_after_quit() -> int:
    print("dog", flush=True)
    for line in sys.stdin:
        command = line.rstrip("\r\n")
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


def _mode_gated_initial() -> int:
    sys.stdout.write("\x1b[?2004h")
    sys.stdout.write("OpenAI Codex\r\n")
    sys.stdout.flush()
    time.sleep(0.05)

    early_ready, _, _ = select.select([sys.stdin], [], [], 0)
    if early_ready:
        early_input = os.read(sys.stdin.fileno(), 4096).decode("utf-8", errors="replace")
        print(f"EARLY_INPUT:{early_input.rstrip()}", flush=True)
    else:
        print("NO_EARLY_INPUT", flush=True)

    sys.stdout.write("\x1b[?25h\x1b[?2026l")
    sys.stdout.flush()
    time.sleep(0.2)

    line = sys.stdin.readline()
    print(f"LATE_INPUT:{line.rstrip()}", flush=True)
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: tty_child.py <mode> [args...]", file=sys.stderr)
        return 2

    mode = argv[1]
    if mode == "echo_initial":
        return _mode_echo_initial()
    if mode == "wait_for_quit":
        return _mode_wait_for_quit()
    if mode == "trailing_after_quit":
        return _mode_trailing_after_quit()
    if mode == "exit_code":
        return _mode_exit_code(argv[2])
    if mode == "silent":
        return _mode_silent()
    if mode == "gated_initial":
        return _mode_gated_initial()

    print(f"unknown mode: {mode}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
