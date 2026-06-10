# `myteam.proto`

Minimum prototype for nested interactive sessions.

## Shape

- `commands.py` is the command-facing API used by `myteam start` and `myteam result`.
- `mothership.py` coordinates the Unix-socket RPC server, session stack, result storage, and active-session switching.
- `pty_process.py` launches and manages one child process attached to one PTY.
- `terminal.py` owns real-terminal raw mode, resize handling, clearing, input, and output.
- `recording.py` captures simple per-session transcripts.
- `protocol.py` contains the tiny JSON RPC client/helpers and shared environment variable names.

## Core behavior

`myteam start` always uses the same request path:

1. If `MYTEAM_MOTHERSHIP_SOCKET` is absent, create a mothership in-process.
2. Send `start_session` to the mothership over its socket.
3. The mothership launches the requested command under a managed PTY.
4. If `MYTEAM_MOTHERSHIP_SOCKET` is present, act as a client/shim: request a child session, poll by request id, print the JSON result, and exit.

Managed child sessions receive:

```text
MYTEAM_MOTHERSHIP_SOCKET=<socket path>
MYTEAM_SESSION_ID=<session id>
```

So a child can call `myteam start ...` to launch a nested session, or `myteam result ...` to report completion.

## Prototype limits

This is intentionally minimal. It demonstrates the process model and does not yet provide durability, authentication, complete job-control semantics, or production-grade cleanup/recovery.
