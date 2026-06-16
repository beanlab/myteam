# Myteam

`myteam` is a framework for building agent harnesses.

```bash
pip install myteam
```

Then start your favorite agent and ask:

```text
Please run `myteam onboard` and briefly explain to me how you can help me build a better harness.
```

See also:

- [governing documents](src/governing_docs) (which is what `myteam onboard` prints).
- [motivating philosophy](src/governing_docs/myteam-philosophy.md)

## Skills and Workflows

**Skills** are simply content-on-demand. They have a description that instructs the agent about when and why to retrieve the associated content.

See [skills.md](src/governing_docs/scenarios/skills.md).

**Workflows** are pipelines of agent sessions. They can be invoked directly by the user, or by an agent as if it were a tool. 

See [workflows.md](src/governing_docs/scenarios/workflows/workflows.md).

## Requirements

- Python 3.11+

## License

MIT
