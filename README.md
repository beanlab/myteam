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

- [demos](src/docs/demos/)
- [users-guide.md](src/myteam/governing_docs/users-guide.md)
- [governing documents](src/myteam/governing_docs) (which is what `myteam onboard` prints).
- [motivating philosophy](src/myteam/governing_docs/myteam-philosophy.md)

## Skills and Workflows

**Skills** are simply content-on-demand. They have a description that instructs the agent about when and why to retrieve the associated content.

See [skills.md](src/myteam/governing_docs/scenarios/skills.md).

**Workflows** are pipelines of agent sessions. They can be invoked directly by the user, or by an agent as if it were a tool. 

See [workflows.md](src/myteam/governing_docs/scenarios/workflows/workflows.md).

## Rosters

Reusable rosters can be listed, downloaded, and updated from GitHub:

```bash
myteam rosters list
myteam rosters download <roster>
myteam rosters update
```

See [roster management](src/myteam/governing_docs/scenarios/rosters.md) for repository, destination, and managed-root options.

## Requirements

- Python 3.11+

## License

MIT
