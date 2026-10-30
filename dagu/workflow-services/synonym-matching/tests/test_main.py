import json
import os
import subprocess
import sys
from pathlib import Path
import jsonschema

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / 'src/main.py'


def run(raw, env_input=None):
    env = {k: v for k, v in os.environ.items() if k != 'TEMPLATE_INPUT'}
    if env_input is not None:
        env['TEMPLATE_INPUT'] = env_input
    return subprocess.run([sys.executable, str(MAIN)], input=raw, capture_output=True, text=True, env=env)


def test_real_output_contract():
    result = run((ROOT / 'examples/input.json').read_text())
    assert result.returncode == 0, result.stderr
    assert len(result.stdout.splitlines()) == 1
    output = json.loads(result.stdout)
    jsonschema.validate(output, json.loads((ROOT / 'schemas/output.schema.json').read_text()))
    assert set(output) == {'synonymMatrix'}
    assert output['synonymMatrix'][0]['referenceElement']['id'] == 'r1'
    assert output['synonymMatrix'][0]['matches'][0]['submissionElement']['id'] == 's2'


def test_environment_precedes_stdin():
    result = run('invalid', (ROOT / 'examples/input.json').read_text())
    assert result.returncode == 0, result.stderr


def test_invalid_and_old_dummy_payloads_fail():
    for payload in ['not-json', '[]', '{}', '{"step":"test"}', '{"input":{"source":"task"}}']:
        result = run(payload)
        assert result.returncode == 1
        assert not result.stdout
        assert '[synonym-matching]' in result.stderr
