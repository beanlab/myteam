from myteam.workflow.steps import AgentContext

AGENT = "undecided"
MODEL = "undecided"

def main():
    if AGENT == "undecided" or MODEL == "undecided":
        raise NotImplementedError(f"Workflow '{__name__}' has not been implemented yet.")
    with AgentContext(usage_logging="summary") as ctx:
        result = ctx.run_agent(
            agent=AGENT,
            model=MODEL,
            prompt="Say 'Ready'",
            output={}
        )
        if result.status != "completed" and result.error_type != 'completion_missing':
            raise RuntimeError(result.error_message)

if __name__ == "__main__":
    main()
