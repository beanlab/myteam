from __future__ import annotations


def test_public_api_imports() -> None:
    from myteam import (  # noqa: PLC0415
        SessionResult,
        UsageInfo,
        explain_resources,
        list_resources,
        load_skill,
        onboard,
        report_workflow_result,
        run_agent,
    )
    from myteam.workflows import (  # noqa: PLC0415
        SessionResult as WorkflowSessionResult,
        UsageInfo as WorkflowUsageInfo,
        report_workflow_result as workflow_report_workflow_result,
        run_agent as workflow_run_agent,
    )

    assert callable(explain_resources)
    assert callable(list_resources)
    assert callable(load_skill)
    assert callable(onboard)
    assert run_agent is workflow_run_agent
    assert report_workflow_result is workflow_report_workflow_result
    assert SessionResult is WorkflowSessionResult
    assert UsageInfo is WorkflowUsageInfo
