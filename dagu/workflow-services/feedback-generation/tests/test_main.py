import json
import subprocess
import sys
from pathlib import Path

MAIN = Path(__file__).resolve().parents[1] / "src" / "main.py"


def test_dummy_output_contract():
    result = subprocess.run([sys.executable, str(MAIN)], input='{"step":"test"}', capture_output=True, text=True)
    output = json.loads(result.stdout)
    assert result.returncode == 0
    assert output["capability"] == "feedback-generation"
    assert output["result"]["feedback"]
