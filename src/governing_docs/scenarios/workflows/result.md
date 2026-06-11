# `myteam result`

`myteam result` is used by agents to reliably return the output requested for that session.

A managed agent session can also end cleanly without calling `myteam result`, for example when a human user or agent enters `/quit`. In that case the session completes with no result: the output is `None` (serialized as JSON `null` by CLI commands). This must be distinguished from reporting `{}`, which is a deliberate empty-object result.

Calling `myteam result` outside a managed session will result in an error.

Agents are instructed on the signature of this command in the content returned by `myteam explain`.

This command communicates the result back to the parent `myteam` process via sockets identified by environment variables. 
