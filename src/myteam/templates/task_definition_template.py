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

from myteam.tasks import AgentContext


def main():
    raise NotImplementedError(f"Task '{__name__}' has not been implemented yet.")
    with AgentContext(usage_logging="summary") as ctx:
        result = ctx.run_agent(
            prompt="Say 'Ready'",
        )
        if result.status != "completed" and result.error_type != 'completion_missing':
            raise RuntimeError(result.error_message)

if __name__ == "__main__":
    main()
