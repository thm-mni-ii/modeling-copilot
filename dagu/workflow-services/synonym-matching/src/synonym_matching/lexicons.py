"""Lokale Synonymlexika ohne Netzwerkzugriff während des Matchings."""

import re
from collections import defaultdict
from pathlib import Path

import numpy as np

from .preprocessing import normalize

DATA_DIR = Path(__file__).resolve().parents[2] / '.cache' / 'lexicons'
# Nur bekannte Registerangaben entfernen, keine beliebigen Klammerausdrücke.
REGISTER_SUFFIX = re.compile(
    r'\s*\((?:ugs\.|fachspr\.|geh\.|Hauptform|Nebenform|veraltet|derb|'
    r'salopp|regional|österr\.|schweiz\.)[^()]*\)\s*$'
)


def key(text):
    """Vereinheitliche Unicode, Leerraum und Großschreibung für die Suche."""
    return normalize(text).lower()


class WordNet:
    """Suche englische Synsets und speichere Ergebnisse pro eindeutigem Label."""

    def __init__(self, path=None):
        """Merke das Datenverzeichnis; geladen wird erst bei der ersten Suche."""
        self.path = Path(path) if path else DATA_DIR / 'nltk_data'
        self.reader = None
        self.cache = {}

    def _load(self):
        """Öffne den lokal installierten WordNet-Korpus, auch als ZIP-Datei."""
        import nltk
        from nltk.corpus.reader import WordNetCorpusReader

        root = None
        locations = ['corpora/wordnet', 'corpora/wordnet.zip/wordnet/']
        for location in locations:
            try:
                root = nltk.data.find(location, paths=[str(self.path)])
                break
            except LookupError:
                continue
        if root is None:
            raise FileNotFoundError(
                'WordNet missing: run python examples/download_lexicons.py'
            )

        # NLTK sucht index.sense zusätzlich über seinen globalen Suchpfad.
        directory = str(self.path.resolve())
        if directory not in nltk.data.path:
            nltk.data.path.insert(0, directory)
        self.reader = WordNetCorpusReader(root, None)

    def lookup(self, text):
        """Liefere Synset-Namen; ein unbekanntes Label ergibt eine leere Menge."""
        text = key(text).replace(' ', '_')
        if not text:
            return frozenset()
        if text not in self.cache:
            if self.reader is None:
                self._load()
            self.cache[text] = frozenset(
                synset.name() for synset in self.reader.synsets(text)
            )
        return self.cache[text]

    def matrix(self, left, right):
        """Vergleiche jedes linke Label mit jedem rechten Label."""
        return synonym_matrix(left, right, self.lookup)


class OpenThesaurus:
    """Suche deutsche Labels in den Synonymgruppen des Text-Exports."""

    def __init__(self, path=None):
        """Merke den Dateipfad; der Export wird bei Bedarf einmal eingelesen."""
        self.path = Path(path) if path else DATA_DIR / 'openthesaurus.txt'
        self.groups = None

    def _load(self):
        """Baue einen Index von Labels auf ihre Gruppennummern auf."""
        groups = defaultdict(set)
        with self.path.open(encoding='utf-8-sig') as stream:
            for index, line in enumerate(stream):
                if not line.strip() or line.lstrip().startswith('#'):
                    continue
                if ';' not in line:
                    continue
                # Eine Exportzeile ist eine Gruppe, Semikolons trennen Wörter.
                for term in line.strip().split(';'):
                    term = key(REGISTER_SUFFIX.sub('', term))
                    if term:
                        groups[term].add(index)
        if not groups:
            raise ValueError('OpenThesaurus file contains no synonym groups')
        self.groups = dict(groups)

    def lookup(self, text):
        """Liefere die Gruppen des Labels, ohne Gruppen transitiv zu verbinden."""
        text = key(text)
        if not text:
            return frozenset()
        if self.groups is None:
            self._load()
        return self.groups.get(text, frozenset())

    def matrix(self, left, right):
        """Vergleiche alle Labelpaare anhand gemeinsamer Synonymgruppen."""
        return synonym_matrix(left, right, self.lookup)


def synonym_matrix(left, right, lookup):
    """Liefere 1 bei gemeinsamem Eintrag, sonst 0; unbekannt ist keine Evidenz."""
    matrix = np.zeros((len(left), len(right)))
    if not left or not right:
        return matrix

    # Mehrfach vorkommende Labels müssen nur einmal nachgeschlagen werden.
    entries = {}
    for text in left + right:
        if text not in entries:
            entries[text] = lookup(text)
    for row, reference_text in enumerate(left):
        for column, student_text in enumerate(right):
            common_entries = entries[reference_text] & entries[student_text]
            matrix[row, column] = float(bool(common_entries))
    return matrix
