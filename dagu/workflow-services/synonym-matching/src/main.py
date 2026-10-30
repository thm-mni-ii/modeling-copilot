#!/usr/bin/env python3
"""CLI-Einstieg: JSON einlesen, Matching ausführen, Synonymmatrix ausgeben."""

import argparse
import json
import os
import sys
from pathlib import Path

import jsonschema

from synonym_matching import MatchingEngine
from synonym_matching.engine import format_synonym_matrix

SERVICE = 'synonym-matching'
SCHEMA_PATH = Path(__file__).resolve().parents[1] / 'schemas/input.schema.json'


def read_input(path=None):
    """Lies die Eingabe aus Datei, TEMPLATE_INPUT oder stdin, in dieser Reihenfolge."""
    if path:
        raw = Path(path).read_text()
    else:
        raw = os.environ.get('TEMPLATE_INPUT')
        if raw is None:
            raw = sys.stdin.read()
    if not raw.strip():
        raise ValueError('TEMPLATE_INPUT or stdin JSON is required')
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError('a JSON object is required')
    return value


def main():
    """Führe einen CLI-Aufruf aus; gib bei Fehlern Exitcode 1 zurück."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', help='JSON file (otherwise TEMPLATE_INPUT or stdin)')
    args = parser.parse_args()
    try:
        payload = read_input(args.input)
        schema = json.loads(SCHEMA_PATH.read_text())
        jsonschema.validate(payload, schema)
        data = payload['input']

        engine = MatchingEngine(data.get('config'))
        result = engine.match(
            data['referenceModel']['elements'],
            data['studentModel']['elements'],
            threshold=data.get('threshold'),
        )
        output = {'synonymMatrix': format_synonym_matrix(result['synonymMatrix'])}
        print(json.dumps(output, ensure_ascii=False, allow_nan=False))
        return 0
    except Exception as error:
        # Kein erfolgreiches Teilergebnis ausgeben, wenn eine Methode scheitert.
        print(f'[{SERVICE}] {type(error).__name__}: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
