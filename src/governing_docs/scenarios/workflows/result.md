# `myteam result`

`myteam result` is used by agents to reliably return the output requested for that session.

Calling `myteam result` outside a managed session will result in an error.

Agents are instructed on the signature of this command in the content returned by `myteam explain`.

This command communicates the result back to the parent `myteam` process via sockets identified by environment variables. 
