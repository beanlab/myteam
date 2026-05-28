"""
This is a template for creating a workflow definition.
Current scaffolding allows for starting an agent with included usage and cost tracking.
"""

from myteam.workflow import AgentContext


def main():
    raise NotImplementedError(f"Workflow '{__name__}' has not been implemented yet.")
    with AgentContext(usage_logging="summary") as ctx:
        result = ctx.run_agent(
            prompt="Say 'Ready'",
        )
        if result.status != "completed" and result.error_type != 'completion_missing':
            raise RuntimeError(result.error_message)

if __name__ == "__main__":
    main()
