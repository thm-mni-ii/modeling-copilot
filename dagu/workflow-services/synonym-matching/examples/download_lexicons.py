"""Explicit one-time download; matching itself stays offline.

OpenThesaurus: https://www.openthesaurus.de/about/download/api (CC BY-SA 4.0).
WordNet: https://wordnet.princeton.edu/license-and-commercial-use
Data and original license notices stay in the ignored .cache directory.
"""
from pathlib import Path
import urllib.request
import zipfile

import nltk

DATA = Path(__file__).resolve().parents[1] / '.cache' / 'lexicons'


def main():
    """Lade die Lexika ausdrücklich herunter; Matching lädt keine Daten nach."""
    DATA.mkdir(parents=True, exist_ok=True)
    archive = DATA / 'openthesaurus.zip'
    if not (DATA / 'openthesaurus.txt').exists():
        url = 'https://www.openthesaurus.de/export/OpenThesaurus-Textversion.zip'
        urllib.request.urlretrieve(url, archive)
        with zipfile.ZipFile(archive) as zipped:
            (DATA / 'openthesaurus.txt').write_bytes(zipped.read('openthesaurus.txt'))
            (DATA / 'LICENSE-OpenThesaurus.txt').write_bytes(zipped.read('LICENSE.txt'))
    nltk.download('wordnet', download_dir=str(DATA / 'nltk_data'), raise_on_error=True)
    print(DATA)


if __name__ == '__main__':
    main()
