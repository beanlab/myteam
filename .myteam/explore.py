from myteam.workflow.steps import AgentContext
from myteam.workflow.models import StepResult

AGENT = "codex"
MODEL = "gpt-5.4-mini"
PROJECT_SETTINGS = {
    # insert needed project sessions to create the issue and attach it to the project correctly
}

def require_completion(result):
    if result.status != "completed" and result.error_type != 'completion_missing':
        raise RuntimeError(result.error_message)
    return result

def explore(ctx: AgentContext) -> StepResult:
    return ctx.run_agent(
        AGENT=AGENT,
        model=MODEL,
        prompt="",
        output={},
    )

def summarize_issue(ctx: AgentContext, transcript) -> StepResult:
    return ctx.run_agent(
        AGENT=AGENT,
        model=MODEL,
        input={"transcript": transcript},
        prompt="",
        output={
            "issue_body": "the body of the issue",
        }
    )

def create_issue(issue_body: str):
    # programmatically creates the issue
    pass

def main():
    with AgentContext(
            usage_logging="summary",
            inactivity_timeout_seconds=900,
    ) as ctx:
        # this should be altered to run the explore process to clearly define the
        explore_result = require_completion(explore(ctx))
        summary_result = require_completion(summarize_issue(ctx, explore_result.transcript))
        create_issue(summary_result.output["issue_body"])
        # summarize the decisions and add to github project and return and output to conclude the workflow automatically
        pass

if __name__ == "__main__":
    main()