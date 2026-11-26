"""Nur OdeNet und das zur Verknüpfung benötigte englische WordNet laden."""

import argparse
from pathlib import Path

import wn

from synonym_matching.lexicons import DATA_DIR


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=DATA_DIR/'wn')
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    wn.config.data_directory = args.directory.resolve()
    for name in ('odenet:1.4', 'omw-en:1.4'):
        if not wn.lexicons(lexicon=name):
            wn.download(name)
    print(args.directory)


if __name__ == '__main__':
    main()
