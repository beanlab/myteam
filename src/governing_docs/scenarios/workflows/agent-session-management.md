# Agent Session Management

`run_agent` spawns an agent CLI session in a child process.

## TTY and Transcript

The stdout/stderr/stdin of the child is wired such that it inherits the TTY of the parent. This creates a transparent UX from the user to the child process.

Stdout/stderr/stdin are also recorded by `myteam` so that a transcript of the session can be returned. This transcript captures the final version of each line as it scrolls off-screen.

## Session Nonce

When a session starts, `myteam` augments the prompt with a session identifier. This unique token is used to identify the conversation on disk so usage information and session ID can be identified reliably. 

## Reporting Results

When a session starts, `myteam` augments the provided prompt with brief instructions detailing the expected output format (using the provided schema) and how to report the result using `myteam result`.

`myteam result` connects to a unique socket on which the parent process is listening to send a JSONL-RPC message with the output JSON. The parent process records the output and terminates the child process. 

