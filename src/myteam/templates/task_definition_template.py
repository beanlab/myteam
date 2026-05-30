"""
name: ""
description: "Unimplemented task"
# Optional task settings (will default to settings in .config.yaml)
agent:
model:
output:
input:
interactive:
session_id:
fork:
extra_args:
usage_logging:
timeout:
"""

from myteam.tasks import AgentContext, StepResult, list_skills, list_tasks


def main() -> StepResult:
    raise NotImplementedError(f"Task '{__name__}' has not been implemented yet.")
    with AgentContext(usage_logging="summary") as ctx:
        result = ctx.run_agent(
            prompt="Say 'Ready'",
            skills=list_skills(),
            tasks=list_tasks(),
        )
        if result.status != "completed" and result.error_type != 'completion_missing':
            raise RuntimeError(result.error_message)

        return result

if __name__ == "__main__":
    main()
