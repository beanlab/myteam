# Workflow Configuration

The file `.myteam.yaml` contains configuration for `myteam` agents. This file (if present) is assumed to be in the working directory.

Configuration for `codex` and `pi` are built-in.

## Agents

The `agent` parameter to a workflow controls which agent executable is used for that session, e.g. `codex` or `pi`.

An agent configuration must be registered for each custom agent. This configuration is a Python file containing a class that is instantiated without arguments and implements the following `AgentConfig` Protocol:

(`UsageInfo` described in `usage.md`)

```python
class AgentSessionContext:
    user_home: Path
    project_root: Path
    launch_cwd: Path


class AgentConfig(Protocol):
    def build_argv(
            self,
            prompt_text: str,
            model: str | None,
            reasoning: str | None,
            interactive: bool,
            session_id: str | None,
            fork: bool,
            extra_args: tuple[str, ...] | None
    ) -> list[str]:
        """Returns the Popen-style args to launch the agent session"""

    def get_exit_sequence(self) -> bytes:
        """Return the text to be sent as input to close the agent session"""

    def locate_session_data(self, nonce: str, context: AgentSessionContext) -> Any:
        """
        Return the location of the session data associated with the provided nonce.
        This typically involves searching the filesystem store of the agent conversations to find the session containing the nonce.
        """

    def get_session_id(self, session_data: Any) -> str:
        """
        Parse the session ID from the given session data. 
        """

    def get_usage_info(self, session_data: Any) -> list[UsageInfo]:
        """
        Parse the UsageInfo from the provided session data.
        """
```

If the agent config module cannot be loaded, an error is raised.

If a given agent runtime does not support all of the provided arguments (e.g. it cannot fork an agent session), then an error should be raised from `build_argv` when unsupported arguments are supplied. 

## Session IDs and Data

`myteam` relies on the underlying agent runtimes for features like model and reasoning settings, session IDs, resuming, and forking. `myteam` is a slim pass-through layer to the underlying agent runtimes. 

## `.myteam.yaml`

`.myteam.yaml` contains workflow argument defaults and custom agent information.

This file lists the agent names and associated Python config file and class name delimited with `::`. The Python config path is relative to the `.myteam.yaml` file.

If you reuse a built-in name, your custom configuration will take precedence over the built-in configuration.

If you want to change default settings, create your own configuration that extends the built-in and adapts the desired behavior.

```yaml
defaults:
  agent: myagent
  model: gpt-5.4-nano
agents:
  myagent: agents/myagent.py::MyAgentConfig
  codex-mini: agents/codex_mini.py::CodexMiniConfig
```
