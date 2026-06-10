import json
from pathlib import Path


def load_workflow_defaults(config_file: Path):
    # TODO - proper error handling
    return json.loads(config_file.read_text())['defaults']
