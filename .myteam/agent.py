from myteam.workflow.steps import AgentContext

AGENT = "codex"
MODEL = "gpt-5.4-mini"

def main():
    with AgentContext() as ctx:
        result = ctx.run_agent(
            agent=AGENT,
            model=MODEL,
            prompt="Say 'Ready'",
            output={}
        )
        if result.status != "completed" and result.error_type != 'completion_missing':
            print(result)
            raise RuntimeError(result.error_message)

if __name__ == "__main__":
    main()