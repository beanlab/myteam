from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path


def _write_role(project: Path, role: str, instructions: str) -> None:
    role_dir = project / ".myteam" / role
    role_dir.mkdir(parents=True)
    (role_dir / "role.md").write_text(f"{instructions}\n", encoding="utf-8")
    (role_dir / "load.py").write_text(
        "#!/usr/bin/env python3\n"
        "from __future__ import annotations\n\n"
        "from pathlib import Path\n\n"
        "from myteam.utils import print_instructions\n\n"
        "def main() -> int:\n"
        "    print_instructions(Path(__file__).resolve().parent)\n"
        "    return 0\n\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )


def _write_fake_workflow_server(script_path: Path) -> None:
    script_path.write_text(
        "#!/usr/bin/env python3\n"
        "from __future__ import annotations\n\n"
        "import json\n"
        "import os\n"
        "import sys\n"
        "from pathlib import Path\n\n"
        "mode = os.environ.get('FAKE_WORKFLOW_MODE', 'success')\n"
        "state_file = os.environ.get('FAKE_WORKFLOW_STATE_FILE')\n"
        "pending = None\n"
        "step_counter = 0\n"
        "turn_counter = 0\n\n"
        "def invocation_count() -> int:\n"
        "    if not state_file:\n"
        "        return 1\n"
        "    path = Path(state_file)\n"
        "    count = 0\n"
        "    if path.exists():\n"
        "        count = int(path.read_text(encoding='utf-8').strip() or '0')\n"
        "    count += 1\n"
        "    path.write_text(str(count), encoding='utf-8')\n"
        "    return count\n\n"
        "invocation = invocation_count()\n\n"
        "def send_response(request_id, result):\n"
        "    sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': request_id, 'result': result}) + '\\n')\n"
        "    sys.stdout.flush()\n\n"
        "def send_notification(method, params):\n"
        "    sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'method': method, 'params': params}) + '\\n')\n"
        "    sys.stdout.flush()\n\n"
        "def parse_payload(params):\n"
        "    text = params['input'][0]['text']\n"
        "    _, _, payload = text.partition('\\n\\n')\n"
        "    return json.loads(payload)\n\n"
        "def complete_turn(thread_id, turn_id, required_keys, payload):\n"
        "    if required_keys == ['summary', 'plandoc']:\n"
        "        output = {'summary': 'plan-summary', 'plandoc': '/plan.md'}\n"
        "    elif required_keys == ['verdict']:\n"
        "        summary = payload['inputs']['summary']\n"
        "        previous = payload['previous_outputs']['plan']['summary']\n"
        "        if summary != 'plan-summary' or previous != 'plan-summary':\n"
        "            output = {'unexpected': 'bad'}\n"
        "        else:\n"
        "            output = {'verdict': 'looks-good'}\n"
        "    else:\n"
        "        output = {key: f'{key}-value' for key in required_keys}\n"
        "    send_notification('item/completed', {\n"
        "        'threadId': thread_id,\n"
        "        'turnId': turn_id,\n"
        "        'item': {\n"
        "            'type': 'agentMessage',\n"
        "            'id': f'item-{turn_id}',\n"
        "            'text': json.dumps(output),\n"
        "        },\n"
        "    })\n"
        "    send_notification('turn/completed', {\n"
        "        'threadId': thread_id,\n"
        "        'turn': {'id': turn_id, 'items': [], 'status': 'completed', 'error': None},\n"
        "    })\n\n"
        "for raw_line in sys.stdin:\n"
        "    line = raw_line.strip()\n"
        "    if not line:\n"
        "        continue\n"
        "    message = json.loads(line)\n"
        "    method = message['method']\n"
        "    params = message.get('params', {})\n"
        "    if method == 'initialize':\n"
        "        send_response(message['id'], {\n"
        "            'userAgent': 'fake-workflow-server',\n"
        "            'codexHome': '/tmp/codex-home',\n"
        "            'platformFamily': 'unix',\n"
        "            'platformOs': 'linux',\n"
        "        })\n"
        "    elif method == 'thread/start':\n"
        "        step_counter += 1\n"
        "        thread_id = f'thread-{step_counter}'\n"
        "        send_response(message['id'], {\n"
        "            'thread': {\n"
        "                'id': thread_id,\n"
        "                'forkedFromId': None,\n"
        "                'preview': 'workflow step',\n"
        "                'ephemeral': False,\n"
        "                'modelProvider': 'fake',\n"
        "                'createdAt': 0,\n"
        "                'updatedAt': 0,\n"
        "                'status': 'idle',\n"
        "                'path': None,\n"
        "                'cwd': params.get('cwd', os.getcwd()),\n"
        "                'cliVersion': 'test',\n"
        "                'source': 'appServer',\n"
        "                'agentNickname': None,\n"
        "                'agentRole': None,\n"
        "                'gitInfo': None,\n"
        "                'name': None,\n"
        "                'turns': [],\n"
        "            },\n"
        "            'model': 'fake-model',\n"
        "            'modelProvider': 'fake',\n"
        "            'serviceTier': None,\n"
        "            'cwd': params.get('cwd', os.getcwd()),\n"
        "            'approvalPolicy': 'never',\n"
        "            'approvalsReviewer': 'user',\n"
        "            'sandbox': {'mode': 'workspace-write'},\n"
        "            'reasoningEffort': None,\n"
        "        })\n"
        "    elif method == 'turn/start':\n"
        "        turn_counter += 1\n"
        "        turn_id = f'turn-{turn_counter}'\n"
        "        properties = params.get('outputSchema', {}).get('properties', {})\n"
        "        missing_type = next((key for key, schema in properties.items() if 'type' not in schema), None)\n"
        "        if missing_type is not None:\n"
        "            sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': message['id'], 'error': {'message': f'missing type for output {missing_type}'}}) + '\\n')\n"
        "            sys.stdout.flush()\n"
        "            continue\n"
        "        required_keys = list(params.get('outputSchema', {}).get('required', []))\n"
        "        payload = parse_payload(params)\n"
        "        send_response(message['id'], {'turn': {'id': turn_id, 'items': [], 'status': 'in_progress', 'error': None}})\n"
        "        send_notification('turn/started', {'threadId': params['threadId'], 'turn': {'id': turn_id, 'items': [], 'status': 'in_progress', 'error': None}})\n"
        "        if mode == 'needs-steer':\n"
        "            pending = {\n"
        "                'thread_id': params['threadId'],\n"
        "                'turn_id': turn_id,\n"
        "                'required_keys': required_keys,\n"
        "                'payload': payload,\n"
        "            }\n"
        "            send_notification('item/agentMessage/delta', {\n"
        "                'threadId': params['threadId'],\n"
        "                'turnId': turn_id,\n"
        "                'itemId': f'item-{turn_id}',\n"
        "                'delta': 'Need clarification',\n"
        "            })\n"
        "            continue\n"
        "        if mode == 'fail-once' and invocation == 1:\n"
        "            send_notification('item/completed', {\n"
        "                'threadId': params['threadId'],\n"
        "                'turnId': turn_id,\n"
        "                'item': {'type': 'agentMessage', 'id': f'item-{turn_id}', 'text': 'not json'},\n"
        "            })\n"
        "            send_notification('turn/completed', {\n"
        "                'threadId': params['threadId'],\n"
        "                'turn': {'id': turn_id, 'items': [], 'status': 'completed', 'error': None},\n"
        "            })\n"
        "            continue\n"
        "        complete_turn(params['threadId'], turn_id, required_keys, payload)\n"
        "        continue\n"
        "    elif method == 'turn/steer':\n"
        "        send_response(message['id'], {'turnId': params['expectedTurnId']})\n"
        "        if pending is None:\n"
        "            continue\n"
        "        steer_text = params['input'][0]['text']\n"
        "        output = {'summary': steer_text, 'plandoc': '/plan.md'}\n"
        "        send_notification('item/completed', {\n"
        "            'threadId': pending['thread_id'],\n"
        "            'turnId': pending['turn_id'],\n"
        "            'item': {'type': 'agentMessage', 'id': f\"item-{pending['turn_id']}\", 'text': json.dumps(output)},\n"
        "        })\n"
        "        send_notification('turn/completed', {\n"
        "            'threadId': pending['thread_id'],\n"
        "            'turn': {'id': pending['turn_id'], 'items': [], 'status': 'completed', 'error': None},\n"
        "        })\n"
        "        pending = None\n",
        encoding="utf-8",
    )


def _server_command(script_path: Path) -> str:
    return f"{shlex.quote(sys.executable)} {shlex.quote(str(script_path))}"


def test_workflows_start_runs_steps_and_persists_outputs(run_myteam, initialized_project: Path):
    _write_role(initialized_project, "plan", "Plan the work")
    _write_role(initialized_project, "review", "Review the work")

    workflow = initialized_project / "workflow.yaml"
    workflow.write_text(
        "plan:\n"
        "  role: .myteam/plan\n"
        "  inputs:\n"
        "    request: draft a plan\n"
        "  outputs:\n"
        "    summary: short plan summary\n"
        "    plandoc: /plan.md\n"
        "review:\n"
        "  role: review\n"
        "  inputs:\n"
        "    summary:\n"
        "      from: plan.summary\n"
        "  outputs:\n"
        "    verdict: review result\n",
        encoding="utf-8",
    )

    fake_server = initialized_project / "fake_workflow_server.py"
    _write_fake_workflow_server(fake_server)

    result = run_myteam(
        initialized_project,
        "workflows",
        "start",
        str(workflow),
        env_overrides={
            "MYTEAM_WORKFLOW_APP_SERVER_COMMAND": _server_command(fake_server),
            "FAKE_WORKFLOW_MODE": "success",
        },
    )

    assert result.exit_code == 0, result.stderr
    assert "completed successfully" in result.stdout

    run_dirs = list((initialized_project / ".myteam" / "workflow_runs").iterdir())
    assert len(run_dirs) == 1
    run_state = json.loads((run_dirs[0] / "run.json").read_text(encoding="utf-8"))
    assert run_state["status"] == "completed"
    assert run_state["completed_outputs"]["plan"] == {
        "summary": "plan-summary",
        "plandoc": "/plan.md",
    }
    assert run_state["completed_outputs"]["review"] == {
        "verdict": "looks-good",
    }

    status_result = run_myteam(initialized_project, "workflows", "status", run_state["run_id"])
    assert status_result.exit_code == 0
    assert "Status: completed" in status_result.stdout
    assert '"verdict": "looks-good"' in status_result.stdout


def test_workflows_start_can_steer_running_step(run_myteam, initialized_project: Path):
    _write_role(initialized_project, "plan", "Plan the work")

    workflow = initialized_project / "workflow.yaml"
    workflow.write_text(
        "plan:\n"
        "  role: plan\n"
        "  inputs:\n"
        "    request: needs clarification\n"
        "  outputs:\n"
        "    summary: short plan summary\n"
        "    plandoc: /plan.md\n",
        encoding="utf-8",
    )

    fake_server = initialized_project / "fake_workflow_server.py"
    _write_fake_workflow_server(fake_server)

    result = run_myteam(
        initialized_project,
        "workflows",
        "start",
        str(workflow),
        input_text="extra detail\n",
        env_overrides={
            "MYTEAM_WORKFLOW_APP_SERVER_COMMAND": _server_command(fake_server),
            "FAKE_WORKFLOW_MODE": "needs-steer",
        },
    )

    assert result.exit_code == 0, result.stderr
    assert "Need clarification" in result.stdout

    run_dirs = list((initialized_project / ".myteam" / "workflow_runs").iterdir())
    run_state = json.loads((run_dirs[0] / "run.json").read_text(encoding="utf-8"))
    assert run_state["completed_outputs"]["plan"]["summary"] == "extra detail"


def test_workflows_resume_retries_failed_step(run_myteam, initialized_project: Path):
    _write_role(initialized_project, "plan", "Plan the work")

    workflow = initialized_project / "workflow.yaml"
    workflow.write_text(
        "plan:\n"
        "  role: plan\n"
        "  inputs:\n"
        "    request: draft a plan\n"
        "  outputs:\n"
        "    summary: short plan summary\n"
        "    plandoc: /plan.md\n",
        encoding="utf-8",
    )

    fake_server = initialized_project / "fake_workflow_server.py"
    _write_fake_workflow_server(fake_server)
    state_file = initialized_project / "fake_server_state.txt"
    env_overrides = {
        "MYTEAM_WORKFLOW_APP_SERVER_COMMAND": _server_command(fake_server),
        "FAKE_WORKFLOW_MODE": "fail-once",
        "FAKE_WORKFLOW_STATE_FILE": str(state_file),
    }

    start_result = run_myteam(
        initialized_project,
        "workflows",
        "start",
        str(workflow),
        env_overrides=env_overrides,
    )
    assert start_result.exit_code == 1
    assert "failed" in start_result.stderr

    run_dirs = list((initialized_project / ".myteam" / "workflow_runs").iterdir())
    run_state = json.loads((run_dirs[0] / "run.json").read_text(encoding="utf-8"))
    assert run_state["status"] == "failed"

    resume_result = run_myteam(
        initialized_project,
        "workflows",
        "resume",
        run_state["run_id"],
        env_overrides=env_overrides,
    )
    assert resume_result.exit_code == 0, resume_result.stderr

    resumed_state = json.loads((run_dirs[0] / "run.json").read_text(encoding="utf-8"))
    assert resumed_state["status"] == "completed"
    assert len(resumed_state["attempts"]["plan"]) == 2
