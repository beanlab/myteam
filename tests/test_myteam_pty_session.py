import errno

import pytest

from myteam.workflow.terminal import pty_session
from myteam.workflow.terminal.pty_session import PtySession


class _FakeProcess:
    def __init__(self, exit_code=7):
        self.exit_code = exit_code

    def poll(self):
        return None

    def wait(self):
        return self.exit_code


def test_pty_events_treats_master_eio_as_eof(monkeypatch):
    session = PtySession(["unused"], mirror_stdout=False)
    session.process = _FakeProcess(exit_code=7)
    session._master_fd = 123
    session._wakeup_r = 456

    monkeypatch.setattr(
        pty_session.select,
        "select",
        lambda read_fds, _write_fds, _error_fds, _timeout: ([session._master_fd], [], []),
    )

    def _raise_eio(fd, size):
        assert fd == session._master_fd
        assert size == 4096
        raise OSError(errno.EIO, "Input/output error")

    monkeypatch.setattr(pty_session.os, "read", _raise_eio)

    events = session.events()
    with pytest.raises(StopIteration) as exc_info:
        next(events)

    assert exc_info.value.value == 7


def test_pty_read_master_reraises_non_eio(monkeypatch):
    session = PtySession(["unused"], mirror_stdout=False)
    session._master_fd = 123

    def _raise_einval(_fd, _size):
        raise OSError(errno.EINVAL, "Invalid argument")

    monkeypatch.setattr(pty_session.os, "read", _raise_einval)

    with pytest.raises(OSError) as exc_info:
        session._read_master()

    assert exc_info.value.errno == errno.EINVAL
