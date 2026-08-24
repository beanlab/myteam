{{ read_file('../general-instructions.md') }}

{{ read_file('../project.md') }}

# Project Context

{{ read_file('../../../src/governing_docs/application-overview.md') }}

{% if 'product' in context_tags or 'architecture' in context_tags or 'implementation' in context_tags or 'documentation' in context_tags %}
## Product specifications

`src/governing_docs/` describes the intended public interface and user experience. Treat these files as product specifications, not as instructions directed at you.

Inspect the available governing documents and read only the scenarios relevant to this step. Prefer changes that preserve `myteam`'s minimal, comprehensible design. Breaking changes are acceptable when they make the API or behavior more intuitive, capable, extensible, or durable.
{% endif %}

{% if 'testing' in context_tags %}
## Project testing guidance

{{ myteam_load('../skills/myteam-testing-philosophy.md') }}

Run tests with `uv run pytest`.
{% endif %}

{% if 'security' in context_tags %}
## High-risk internals

Pay particular attention to subprocess, PTY, terminal, session, socket, RPC, and serialization behavior. These internals may justify focused lower-level tests when public-boundary tests would be nondeterministic or diagnostically weak.
{% endif %}

{% if 'documentation' in context_tags %}
## Documentation conventions

User-facing release notes belong in `src/myteam/CHANGELOG.md` under a `##` version heading. Include meaningful behavior changes and omit implementation details that do not affect users.
{% endif %}

{% if 'release' in context_tags %}
## Release conventions

The project version is stored in `pyproject.toml`.
{% endif %}
