from myteam.workflow.steps import AgentContext

def main():
    with AgentContext(usage_logging="summary") as ctx:
        result = ctx.run_agent(
            prompt="Say 'Ready'",
        )
        if result.status != "completed" and result.error_type != 'completion_missing':
            raise RuntimeError(result.error_message)

if __name__ == "__main__":
    main()