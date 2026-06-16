# Python API

Most commands in the `myteam` CLI are intended to be run by agents in order to augment the agent context with intended information.

A similar need exists when designing and agent workflow: the prompt must be prepared with the intended information.

All CLI commands for retrieving agent instructions should also be provided as importable Python methods. These methods should return (as a string) the exact same content as the CLI commands print to stdout.
