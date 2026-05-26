import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_agent_package_imports_when_process_starts_from_ui_directory():
    """pulsar-agent must be importable as an installed package from any cwd."""
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    result = subprocess.run(
        [sys.executable, "-c", "from pulsar_agent.graph import answer_question; print(answer_question.__name__)"],
        cwd=ROOT / "pulsar-ui",
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "answer_question"
