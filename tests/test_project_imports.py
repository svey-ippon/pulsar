import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_agent_package_imports_when_process_starts_from_app_directory():
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    result = subprocess.run(
        [sys.executable, "-c", "from agent.graph import answer_question; print(answer_question.__name__)"],
        cwd=ROOT / "app",
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "answer_question"
