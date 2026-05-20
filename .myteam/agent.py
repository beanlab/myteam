from myteam.workflow.steps import AgentContext

AGENT = "codex"

def main():
    with AgentContext() as ctx:
        result = ctx.run_agent(
            agent=AGENT,
            prompt="Ask the user what they want to work on.",
            output={}
        )
        if result.status != "completed" and result.error_type != 'completion_missing':
            print(result)
            raise RuntimeError(result.error_message)

if __name__ == "__main__":
    main()