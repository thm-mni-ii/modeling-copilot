#!/usr/bin/env python3
"""Ein JSON-Aufruf der ausgewählten Pipeline auf frischen Labels."""

import argparse
import json
import os
from pathlib import Path
import sys

import jsonschema

from synonym_matching import MatchingPipeline

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, help='sonst TEMPLATE_INPUT oder stdin')
    args = parser.parse_args()
    try:
        raw = args.input.read_text() if args.input else os.environ.get('TEMPLATE_INPUT')
        payload = json.loads(sys.stdin.read() if raw is None else raw)
        jsonschema.validate(payload, json.loads((ROOT/'schemas/input.schema.json').read_text()))
        data = payload['input']
        options = dict(data.get('config', {}))
        if 'threshold' in data:
            options['meaning_threshold'] = data['threshold']
        result = MatchingPipeline(**options).match(data['referenceModel']['elements'], data['studentModel']['elements'])
        jsonschema.validate(result, json.loads((ROOT/'schemas/output.schema.json').read_text()))
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except Exception as error:
        message = error.message if isinstance(error, jsonschema.ValidationError) else str(error)
        print(f'[synonym-matching-louis] {type(error).__name__}: {message}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
