from __future__ import annotations

import signal
import select
import sys
import time


def _mode_echo_initial() -> int:
    print("READY", flush=True)
    line = sys.stdin.readline()
    print(f"ECHO:{line.rstrip()}", flush=True)
    return 0


def _mode_reject_early_initial() -> int:
    ready, _, _ = select.select([sys.stdin], [], [], 0.1)
    if ready:
        line = sys.stdin.readline()
        print(f"EARLY_INPUT:{line.rstrip()}", flush=True)
        return 3

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


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: tty_child.py <mode> [args...]", file=sys.stderr)
        return 2

    mode = argv[1]
    if mode == "echo_initial":
        return _mode_echo_initial()
    if mode == "reject_early_initial":
        return _mode_reject_early_initial()
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
