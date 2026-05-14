from __future__ import annotations

from collections.abc import Generator, Mapping
from queue import Empty, Queue
import errno
import os
import pty
import select
import shutil
import signal
import subprocess
import sys
import termios
import time
import tty


class PtySession:
    def __init__(
        self,
        argv: list[str],
        *,
        env: Mapping[str, str] | None = None,
        inactivity_timeout_seconds: int = 600,
        mirror_stdout: bool = True,
        forward_stdin: bool = True,
    ) -> None:
        self.argv = argv
        self.env = None if env is None else dict(env)
        self.inactivity_timeout_seconds = inactivity_timeout_seconds
        self.mirror_stdout = mirror_stdout
        self.forward_stdin = forward_stdin
        self.process: subprocess.Popen[bytes] | None = None
        self._master_fd = -1
        self._slave_fd = -1
        self._stdin_fd: int | None = None
        self._restore_tty: list[int] | None = None
        self._previous_winch_handler = None
        self._input_queue: Queue[bytes] = Queue()
        self._wakeup_r = -1
        self._wakeup_w = -1
        self._stdin_closed = False

    def __enter__(self) -> "PtySession":
        self._master_fd, self._slave_fd = pty.openpty()
        self._wakeup_r, self._wakeup_w = os.pipe()
        os.set_blocking(self._wakeup_r, False)
        self._copy_terminal_size()
        self.process = subprocess.Popen(
            self.argv,
            stdin=self._slave_fd,
            stdout=self._slave_fd,
            stderr=self._slave_fd,
            env=None if self.env is None else {**os.environ, **self.env},
            start_new_session=True,
            close_fds=True,
        )
        os.close(self._slave_fd)
        self._slave_fd = -1

        if self.forward_stdin and sys.stdin.isatty():
            self._stdin_fd = sys.stdin.fileno()
            self._restore_tty = termios.tcgetattr(self._stdin_fd)
            tty.setraw(self._stdin_fd)

        self._previous_winch_handler = signal.getsignal(signal.SIGWINCH)
        signal.signal(signal.SIGWINCH, self._handle_winch)
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=0.2)
            except subprocess.TimeoutExpired:
                self.process.kill()
        if self._previous_winch_handler is not None:
            signal.signal(signal.SIGWINCH, self._previous_winch_handler)
        if self._restore_tty is not None and self._stdin_fd is not None:
            termios.tcsetattr(self._stdin_fd, termios.TCSADRAIN, self._restore_tty)
        for fd in (self._master_fd, self._slave_fd, self._wakeup_r, self._wakeup_w):
            if fd >= 0:
                try:
                    os.close(fd)
                except OSError:
                    pass

    def enqueue_input(self, data: bytes) -> None:
        if not data:
            return
        self._input_queue.put(data)
        os.write(self._wakeup_w, b"x")

    def events(self) -> Generator[bytes, None, int]:
        if self.process is None:
            raise RuntimeError("PtySession must be entered before iterating events().")

        last_output_at = time.monotonic()
        while True:
            if self.process.poll() is not None:
                chunk = self._read_master()
                if chunk:
                    if self.mirror_stdout:
                        os.write(sys.stdout.fileno(), chunk)
                    yield chunk
                    last_output_at = time.monotonic()
                    continue
                return self.process.wait()

            timeout = max(0.0, self.inactivity_timeout_seconds - (time.monotonic() - last_output_at))
            read_fds = [self._master_fd, self._wakeup_r]
            if self._stdin_fd is not None and not self._stdin_closed:
                read_fds.append(self._stdin_fd)

            ready, _, _ = select.select(read_fds, [], [], timeout)
            if not ready:
                raise TimeoutError(
                    f"PTY session became inactive for {self.inactivity_timeout_seconds} seconds."
                )

            if self._wakeup_r in ready:
                self._drain_wakeup_pipe()
                self._flush_enqueued_input()

            if self._master_fd in ready:
                chunk = self._read_master()
                if not chunk:
                    return self.process.wait()
                if self.mirror_stdout:
                    os.write(sys.stdout.fileno(), chunk)
                yield chunk
                last_output_at = time.monotonic()

            if self._stdin_fd is not None and self._stdin_fd in ready:
                parent_input = os.read(self._stdin_fd, 4096)
                if not parent_input:
                    self._stdin_closed = True
                else:
                    self._write_all(parent_input)

    def _read_master(self) -> bytes:
        try:
            return os.read(self._master_fd, 4096)
        except OSError as exc:
            if exc.errno == errno.EIO:
                return b""
            raise

    def _flush_enqueued_input(self) -> None:
        while True:
            try:
                self._write_all(self._input_queue.get_nowait())
            except Empty:
                return

    def _write_all(self, data: bytes) -> None:
        view = memoryview(data)
        while view:
            written = os.write(self._master_fd, view)
            view = view[written:]

    def _drain_wakeup_pipe(self) -> None:
        try:
            while True:
                if not os.read(self._wakeup_r, 4096):
                    return
        except (BlockingIOError, OSError):
            return

    def _copy_terminal_size(self) -> None:
        size = shutil.get_terminal_size(fallback=(80, 24))
        if sys.stdin.isatty():
            packed = termios.tcgetwinsize(sys.stdin.fileno())
        else:
            packed = (size.lines, size.columns)
        termios.tcsetwinsize(self._master_fd, packed)

    def _handle_winch(self, _signum: int, _frame: object) -> None:
        try:
            self._copy_terminal_size()
        except OSError:
            pass
