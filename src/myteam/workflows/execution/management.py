import subprocess
from pathlib import Path


class WorkflowManager:
    def __init__(self):
        self._running_workflows = []
        self._requested_workflows = []

    def run_soon(self, workflow_file: Path, workflow_input: str | None):
        pass  # Send signal containing workflow-file and workflow_input
        
    def run_workflow_engine(self):
        while self._running_workflows:
            try:
                next(self._running_workflows[-1])
                # if next returns, the workflow is complete, and we get a stop iteration
                # if next yields, it is not complete, and we should start the queue workflow
                self._running_workflows.append(self._start_requested_workflow())
            except StopIteration:  # completed
                self._running_workflows.pop()
            
    def _start_requested_workflow(self):
        workflow_file, workflow_input = self._requested_workflows.pop(0)
        self._running_workflows.append(self._start_workflow(workflow_file, workflow_input))
        
    def _start_workflow(self, workflow_file: Path, workflow_input: str | None):
        while True:
            session = start_agent_session(workflow)
            # exited - is a new workflow queued?
            if self._
                