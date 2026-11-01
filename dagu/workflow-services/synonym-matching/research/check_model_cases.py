"""Ein Einstieg für alle Forschungsläufe: Konfigurationen vergleichen, JSON speichern."""

import argparse
import json
from pathlib import Path

from .experiments import run_experiments


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=Path(__file__).with_name('model-cases.json'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--models', action='store_true', help='Embedding- und Übersetzungsverfahren')
    parser.add_argument('--lexicons', action='store_true', help='WordNet und OpenThesaurus')
    parser.add_argument('--threshold', type=float, default=.5)
    parser.add_argument('--preprocessing', nargs='*', default=None,
                        help='Nur diese Schritte vergleichen; ohne Angabe alle Ablationen')
    parser.add_argument('--extended', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    pipelines = None if args.preprocessing is None else {'custom': args.preprocessing}
    errors = run_experiments(
        json.loads(args.data.read_text()), args.output,
        models=args.models, lexicons=args.lexicons, threshold=args.threshold,
        pipelines=pipelines,
    )
    print(f'Gespeichert: {args.output}; technische Fehler: {len(errors)}')
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
