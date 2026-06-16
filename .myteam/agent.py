"""
name: "Test Agent"
description: "This is a test agent task"
"""

from myteam.tasks import AgentContext, StepResult, list_tasks, list_skills


def main():
    with AgentContext(usage_logging="summary", timeout=900) as ctx:
        result = ctx.run_agent(
            prompt="Say 'Ready'",
            skills=list_skills(),
            tasks=list_tasks(),
        )
        if result.status != "completed" and result.error_type != 'completion_missing':
            raise RuntimeError(result.error_message)

if __name__ == "__main__":
    main()
