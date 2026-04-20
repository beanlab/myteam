from __future__ import annotations

from pathlib import Path

import pytest

from myteam.workflow.parser import load_workflow


def test_load_workflow_accepts_documented_workflow_shape(tmp_path: Path):
    workflow_file = tmp_path / "haikus.yaml"
    workflow_file.write_text(
        "step1:\n"
        "  prompt: I need three haikus. Please write them for me.\n"
        "  output:\n"
        "    haiku_dogs: A haiku about dogs\n"
        "    haiku_cats: A haiku about cats\n"
        "    haiku_user_choice: A haiku about a topic provided by the user\n"
        "step2:\n"
        "  input: $step1.output\n"
        "  prompt: |\n"
        "    Review the provided haikus.\n"
        "    Rank them in terms of which best captures the essence and style of haiku.\n"
        "  output:\n"
        "    best_haiku:\n"
        "      haiku: the haiku text\n"
        "      reason: why this haiku was chosen over the others\n",
        encoding="utf-8",
    )

    workflow = load_workflow(workflow_file)

    assert list(workflow) == ["step1", "step2"]
    assert workflow["step1"]["prompt"] == "I need three haikus. Please write them for me."
    assert workflow["step2"]["input"] == "$step1.output"
    assert workflow["step2"]["output"]["best_haiku"]["haiku"] == "the haiku text"


def test_load_workflow_accepts_scalar_output_template(tmp_path: Path):
    workflow_file = tmp_path / "scalar.yaml"
    workflow_file.write_text(
        "step1:\n"
        "  prompt: hello\n"
        "  output: concise answer\n",
        encoding="utf-8",
    )

    workflow = load_workflow(workflow_file)

    assert workflow["step1"]["output"] == "concise answer"


def test_load_workflow_rejects_steps_wrapper(tmp_path: Path):
    workflow_file = tmp_path / "wrapped.yaml"
    workflow_file.write_text(
        "steps:\n"
        "  step1:\n"
        "    prompt: hello\n"
        "    output:\n"
        "      message: hi\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Workflow step 'steps' has unsupported keys: step1."):
        load_workflow(workflow_file)


def test_load_workflow_rejects_unknown_step_keys(tmp_path: Path):
    workflow_file = tmp_path / "extra-key.yaml"
    workflow_file.write_text(
        "step1:\n"
        "  prompt: hello\n"
        "  output:\n"
        "    message: hi\n"
        "  timeout: 30\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unsupported keys: timeout"):
        load_workflow(workflow_file)


def test_load_workflow_rejects_non_identifier_keys_anywhere_in_structure(tmp_path: Path):
    workflow_file = tmp_path / "bad-keys.yaml"
    workflow_file.write_text(
        "step1:\n"
        "  prompt: hello\n"
        "  input:\n"
        "    bad-key: value\n"
        "  output:\n"
        "    message: hi\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="non-identifier key: 'bad-key'"):
        load_workflow(workflow_file)


def test_load_workflow_rejects_unknown_agents(tmp_path: Path):
    workflow_file = tmp_path / "agent.yaml"
    workflow_file.write_text(
        "step1:\n"
        "  agent: mystery\n"
        "  prompt: hello\n"
        "  output:\n"
        "    message: hi\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unknown workflow agent: mystery"):
        load_workflow(workflow_file)


def test_load_workflow_rejects_list_output_template(tmp_path: Path):
    workflow_file = tmp_path / "list-output.yaml"
    workflow_file.write_text(
        "step1:\n"
        "  prompt: hello\n"
        "  output:\n"
        "    - nope\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must be a mapping or scalar, not a list"):
        load_workflow(workflow_file)
