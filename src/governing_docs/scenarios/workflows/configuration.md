# Workflow Configuration

The files `~/.myteam.yaml` and `.myteam.yaml` contain configuration for `myteam` agents. The home file applies globally, and the project file (if present) is read from the working directory. There is no opt-out for the home file.

Configuration for `codex`, `pi`, and `claude` is built in.

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
            extra_args: tuple[str, ...] | None,
            session_name: str | None = None,
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

Adapter parameters are opt-in: `myteam` passes only the supported keyword names declared by `build_argv`, so existing adapters do not need to declare `session_name`. An adapter that declares `session_name: str | None = None` receives the explicit or configured name, or `None` when neither exists.

If a given agent runtime does not support all of the provided arguments (e.g. it cannot fork an agent session), then an error should be raised from `build_argv` when unsupported arguments are supplied. 

## Session IDs and Data

`myteam` relies on the underlying agent runtimes for features like model and reasoning settings, session IDs, resuming, and forking. `myteam` is a slim pass-through layer to the underlying agent runtimes. 

## `.myteam.yaml`

A `.myteam.yaml` file contains workflow argument defaults and custom agent information. `~/.myteam.yaml` provides reusable defaults and agents for every project; the working directory's `.myteam.yaml` customizes them for that project.

Defaults merge by field, with the project file taking precedence. A project field that is omitted inherits the global value. A project field explicitly set to `null` clears the global value. Every provided field replaces the global field as a whole; collection-valued fields such as `extra_args` are not appended.

Agent maps merge by name. Project agents override global agents with the same name, while other global agents remain available. In either file, `agents` maps an agent name to its Python config file, optionally followed by a class name delimited with `::`. A relative Python config path is resolved from the directory containing the `.myteam.yaml` file that defined that agent.

If you reuse a built-in name, your custom configuration will take precedence over the built-in configuration.

Every participating file is parsed and validated. An invalid home or project file is fatal, even when the other file is valid, and the error identifies the invalid file. If the home and project paths refer to the same physical file, it is treated as one source.

If you want to change default settings, create your own configuration that extends the built-in and adapts the desired behavior.

```yaml
defaults:
  agent: myagent
  session_name: Review API
  model: gpt-5.4-nano
agents:
  myagent: agents/myagent.py::MyAgentConfig
  codex-mini: agents/codex_mini.py::CodexMiniConfig
```

`defaults.session_name` supplies the lifecycle display name when a `run_agent` call does not provide one and is forwarded to adapters that opt into native session naming. Empty names are valid and forwarded, non-string YAML values are converted to text, and names containing carriage returns or line feeds are rejected. When no explicit or configured name exists, the lifecycle display uses `New session`, but adapters receive `None`.
