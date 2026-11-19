"""Explicit one-time download; matching itself stays offline.

OpenThesaurus: https://www.openthesaurus.de/about/download/api (CC BY-SA 4.0).
WordNet: https://wordnet.princeton.edu/license-and-commercial-use
Data and original license notices stay in the ignored .cache directory.
"""
import argparse
from pathlib import Path
import urllib.request
import zipfile

import wn

DATA = Path(__file__).resolve().parents[1] / '.cache' / 'lexicons'


def download_wordnet(version):
    """Lade eine feste WordNet-Ausgabe in den gemeinsamen wn-Cache."""
    directory = DATA / 'wn'
    directory.mkdir(parents=True, exist_ok=True)
    wn.config.data_directory = directory
    wn.download(version)


def main():
    """Lade die Lexika ausdrücklich herunter; Matching lädt keine Daten nach."""
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument('--odenet', action='store_true', help='Nur OdeNet 1.4 laden')
    selection.add_argument('--wordnet', action='store_true', help='Nur englisches WordNet omw-en:1.4 laden')
    args = parser.parse_args()
    if args.odenet or args.wordnet:
        download_wordnet('odenet:1.4' if args.odenet else 'omw-en:1.4')
        print(DATA / 'wn')
        return
    DATA.mkdir(parents=True, exist_ok=True)
    archive = DATA / 'openthesaurus.zip'
    if not (DATA / 'openthesaurus.txt').exists():
        url = 'https://www.openthesaurus.de/export/OpenThesaurus-Textversion.zip'
        urllib.request.urlretrieve(url, archive)
        with zipfile.ZipFile(archive) as zipped:
            (DATA / 'openthesaurus.txt').write_bytes(zipped.read('openthesaurus.txt'))
            (DATA / 'LICENSE-OpenThesaurus.txt').write_bytes(zipped.read('LICENSE.txt'))
    download_wordnet('omw-en:1.4')
    print(DATA)


if __name__ == '__main__':
    main()
