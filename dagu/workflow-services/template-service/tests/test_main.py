import json
import subprocess
import sys
from pathlib import Path

MAIN = Path(__file__).resolve().parents[1] / "src" / "main.py"


def run(env_extra=None, stdin_input=None):
    env = {"PATH": "/usr/bin:/bin"}
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(MAIN)],
        input=stdin_input,
        capture_output=True,
        text=True,
        env=env,
    )


def test_success_via_env_var():
    result = run(env_extra={"TEMPLATE_INPUT": json.dumps({"message": "hi"})})
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["status"] == "ok"
    assert output["echo"] == {"message": "hi"}


def test_success_via_stdin():
    result = run(stdin_input=json.dumps({"message": "hi"}))
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["echo"]["message"] == "hi"


def test_failure_on_invalid_input():
    result = run(stdin_input="not json")
    assert result.returncode == 1
    assert "invalid input" in result.stderr
