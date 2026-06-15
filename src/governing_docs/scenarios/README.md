# Myteam Interface Scenarios

Scenario documentation is the authoritative documentation model for
externally observable `myteam` behavior.

# Context

`myteam` is a command-line application for building file-based agent systems.
It operates relative to the current working directory, treats that directory as
the project root, and uses a selected project-local root for commands that
create, load, remove, download, update, or start local agent-system objects.

The default project-local root is `.myteam/`. Supported commands can select a
different local root with `--prefix <path>`.

Roles, skills, workflows, tools, and managed roster installs are represented by
files and directories. Callers interact with those objects through the CLI and
observe behavior through standard output, standard error, exit status, and
filesystem changes under the current project.

# Scenario Groups

- [Local tree management](local_tree/manages_local_tree.md)
- [Selected local roots](local_tree/uses_selected_local_root.md)
- [Instruction loading](instruction_loading/loads_instruction_nodes.md)
- [Upgrade guidance](instruction_loading/surfaces_upgrade_guidance.md)
- [Workflow execution](workflows/runs_workflows.md)
- [Workflow definition validation](workflows/validates_workflow_definitions.md)
- [Workflow result submission](workflows/submits_workflow_results.md)
- [Roster management](rosters/manages_rosters.md)
- [CLI status reporting](diagnostics/reports_cli_status.md)

# Non-Goals

These scenarios do not define internal module boundaries, template
implementation details, private helper behavior, the prose content of any
project's role or skill instructions, or the contents of any external roster
repository.
