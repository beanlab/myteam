# Workflow Configuration

The preferred configuration files are `~/.myteam/config.yaml` and `.myteam/config.yaml`. The home file applies globally, and the project file (if present) is read from the working directory. There is no opt-out for the home file.

The files `~/.myteam.yaml` and `.myteam.yaml` are deprecated fallbacks. If either deprecated file is present, `myteam` emits a warning. If both the preferred and deprecated file exist at the same scope, the preferred file is used and the deprecated file is ignored.

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
            prompt_text: str | None,
            model: str | None,
            reasoning: str | None,
            interactive: bool,
            session_id: str | None,
            fork: bool,
            extra_args: tuple[str, ...] | None,
            session_name: str | None = None,
            system_prompt: str | None = None,
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

Every adapter must accept every `build_argv` parameter in the protocol. `myteam` always passes the complete set as keyword arguments, including arguments whose values are `None` or otherwise inactive. Adapters may implement, transform, reject, or ignore each argument as appropriate for the underlying agent runtime. Omitting a supported parameter from an adapter is an error when `build_argv` is called.

The adapter receives the rendered user prompt separately from the effective system prompt, which contains caller-supplied system content followed by `myteam`'s framework instructions. An adapter may preserve that distinction, concatenate the prompts, or ignore either value according to the behavior it provides. `prompt_text` is `None` when the session should start without user input. `session_name` contains the explicit or configured name, including an empty string, or `None` when neither exists.

The built-in Pi and Claude adapters pass system-prompt content with `--append-system-prompt`. The built-in Codex adapter passes it with the `developer-instructions` configuration override.

When the underlying runtime does not support an argument, the adapter decides whether to reject that value, approximate the behavior, or ignore it.

## Session IDs and Data

`myteam` relies on the underlying agent runtimes for features like model and reasoning settings, session IDs, resuming, and forking. `myteam` is a slim pass-through layer to the underlying agent runtimes. 

## `.myteam/config.yaml`

A `config.yaml` file inside `.myteam/` contains workflow argument defaults, custom agent information, and Jinja function registrations. `~/.myteam/config.yaml` provides reusable configuration for every project; the working directory's `.myteam/config.yaml` customizes it for that project.

Defaults merge by field, with the project file taking precedence. A project field that is omitted inherits the global value. A project field explicitly set to `null` clears the global value. Every provided field replaces the global field as a whole; collection-valued fields such as `extra_args` are not appended.

Agent maps merge by name. Project agents override global agents with the same name, while other global agents remain available. In either file, `agents` maps an agent name to its Python config file, optionally followed by a class name delimited with `::`. A relative Python config path is resolved from the directory containing the `config.yaml` file that defined that agent.



If you reuse a built-in agent name, your custom configuration will take precedence over the built-in configuration.

Jinja function maps also merge by name, with project registrations overriding global registrations. Each `jinja_functions` value must use `file.py::function_name`. Relative Python file paths resolve from the directory containing the `config.yaml` file that registered the function. There is no syntax for removing a global registration.

See [Jinja2 Template Rendering](../jinja-support.md) for function loading, precedence, and security behavior.

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
jinja_functions:
  slugify: helpers/jinja.py::slugify
  issue_url: helpers/jinja.py::issue_url
```

`defaults.session_name` supplies the lifecycle display name when a `run_agent` call does not provide one and is forwarded to adapters. Empty names are valid and forwarded, non-string YAML values are converted to text, and names containing carriage returns or line feeds are rejected. When no explicit or configured name exists, the lifecycle display uses `New session`, but adapters receive `None`.
