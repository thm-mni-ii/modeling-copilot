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
    """Lokaler wn-Zugriff auf englisches WordNet 3.0 mit Wortformensuche.

    Ein gemeinsamer Synset ist Evidenz für eine mögliche gemeinsame Lesart,
    keine Bestimmung der fachlich passenden Bedeutung im Modell.
    """

    version = 'omw-en:1.4'
    language = 'en'

    def __init__(self, path=None):
        """Merke den gemeinsamen wn-Datenpfad; lade erst bei der ersten Suche."""
        self.path = Path(path) if path else DATA_DIR / 'wn'
        self.reader = None
        self.morphy = None
        self.cache = {}

    def _load(self):
        """Öffne nur lokale Daten; Englisch bekommt zusätzlich Morphy."""
        import wn

        command = '--wordnet' if self.language == 'en' else '--odenet'
        message = (f'{type(self).__name__} missing ({self.version}): '
                   f'run python scripts/download_lexicons.py {command}')
        if not (self.path / 'wn.db').is_file():
            raise FileNotFoundError(message)
        wn.config.data_directory = self.path.resolve()
        if not wn.lexicons(lexicon=self.version):
            raise FileNotFoundError(message)
        if self.language == 'en':
            from wn.morphy import Morphy

            # Exakte englische Lemmasuche plus explizite Wortformen, wie bisher.
            self.reader = wn.Wordnet(self.version, normalizer=None, search_all_forms=False)
            self.morphy = Morphy(self.reader)
        else:
            # Für OdeNet muss die Normalisierung zum wn-Suchindex passen.
            self.reader = wn.Wordnet(self.version)

    def lookup(self, text):
        """Cache alle möglichen Synsets pro Label; unbekannte Labels bleiben leer."""
        if self.language == 'en':
            text = text.replace('_', ' ')
        text = key(text)
        if not text:
            return frozenset()
        if text not in self.cache:
            if self.reader is None:
                self._load()
            forms = self.morphy(text) if self.morphy else {}
            if not forms:
                forms = {None: {text}}
            if 'a' in forms:
                # OMW führt adjective satellites separat als 's'; Morphy liefert 'a'.
                forms['s'] = forms['a']
            self.cache[text] = frozenset(
                synset.id for pos, words in forms.items() for word in words
                for synset in self.reader.synsets(word, pos=pos))
        return self.cache[text]

    def matrix(self, left, right):
        """Liefere 1 bei gemeinsamem Synset, sonst 0; Unbekanntes ist keine Evidenz."""
        return synonym_matrix(left, right, self.lookup)


class OdeNet(WordNet):
    """Nutze denselben lokalen Zugriff für Deutsch, ohne englische Morphologie."""

    version = 'odenet:1.4'
    language = 'de'


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
