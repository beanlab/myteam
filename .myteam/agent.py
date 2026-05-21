from myteam.workflow.steps import AgentContext

AGENT = "codex"
MODEL = "gpt-5.4-mini"

def main():
    with AgentContext(
            usage_logging="summary",
            inactivity_timeout_seconds=900,
    ) as ctx:
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