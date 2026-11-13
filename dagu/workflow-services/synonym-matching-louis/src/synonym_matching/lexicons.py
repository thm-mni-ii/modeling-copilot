"""Lokale Synonymlexika ohne Netzwerkzugriff während des Matchings."""

import re
from collections import defaultdict
from pathlib import Path

import numpy as np

from .preprocessing import normalize

DATA_DIR = Path(__file__).resolve().parents[2] / '.cache' / 'lexicons'
RELATION_FEATURES = (
    'pair_known', 'reference_synset_count', 'student_synset_count',
    'reference_hypernym', 'reference_hyponym', 'antonym',
    'path_similarity', 'wup_similarity', 'taxonomy_available',
)
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
        self.relation_cache = {}
        self.ancestor_cache = {}
        self.similarity_cache = {}
        self.translation_cache = {}

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

    def _key(self, text):
        """Verwende für Caches und Relationssuche dieselbe Schreibweise."""
        if self.language == 'en':
            text = text.replace('_', ' ')
        return key(text)

    def _forms(self, text):
        """Liefere dieselben Wortformen für Synsets und wortbezogene Antonyme."""
        forms = self.morphy(text) if self.morphy else {}
        if not forms:
            forms = {None: {text}}
        if 'a' in forms:
            # OMW führt adjective satellites separat als 's'; Morphy liefert 'a'.
            forms['s'] = forms['a']
        return forms

    def lookup(self, text):
        """Cache alle möglichen Synsets pro Label; unbekannte Labels bleiben leer."""
        text = self._key(text)
        if not text:
            return frozenset()
        if text not in self.cache:
            if self.reader is None:
                self._load()
            self.cache[text] = frozenset(
                synset.id for pos, words in self._forms(text).items() for word in words
                for synset in self.reader.synsets(word, pos=pos))
        return self.cache[text]

    def translate(self, text, target='omw-en:1.4'):
        """Cache die native Synsetübersetzung, ohne eine Lesart auszuwählen."""
        cache_key = (self._key(text), target)
        if cache_key not in self.translation_cache:
            self.translation_cache[cache_key] = frozenset(
                translated.id for identifier in self.lookup(text)
                for translated in self.reader.synset(identifier).translate(lexicon=target))
        return self.translation_cache[cache_key]

    def _ancestors(self, synset):
        """Nutze die native transitive Oberbegriffssuche von wn."""
        if synset.id not in self.ancestor_cache:
            self.ancestor_cache[synset.id] = frozenset(
                node.id for node in synset.closure('hypernym', 'instance_hypernym')
                if node.id != synset.id)
        return self.ancestor_cache[synset.id]

    def _relation_profile(self, text):
        """Cache Relationsevidenz für alle möglichen Lesarten eines Labels."""
        text = self._key(text)
        cache_key = text
        if cache_key not in self.relation_cache:
            ids = self.lookup(text)
            nodes = [self.reader.synset(identifier) for identifier in ids]
            ancestors, antonym_synsets, sense_ids, antonym_senses = set(), set(), set(), set()
            for node in nodes:
                ancestors.update(self._ancestors(node))
                antonym_synsets.update(s.id for s in node.relations('antonym').get('antonym', []))
            if ids:
                # Keine Antonyme anderer Wörter desselben Synsets übernehmen.
                for pos, words in self._forms(text).items():
                    for word in words:
                        for sense in self.reader.senses(word, pos=pos):
                            sense_ids.add(sense.id)
                            antonym_senses.update(s.id for s in sense.relations('antonym').get('antonym', []))
            self.relation_cache[cache_key] = {
                'synsets': ids, 'nodes': nodes, 'ancestors': ancestors, 'antonym_synsets': antonym_synsets,
                'senses': sense_ids, 'antonym_senses': antonym_senses,
            }
        return self.relation_cache[cache_key]

    def _taxonomy_similarity(self, first, second):
        """Maximiere native Metriken über verbundene Nomen-/Verb-Lesarten.

        Das Maximum ist eine optimistische Zusammenfassung, keine Disambiguierung.
        Keine künstliche Wurzel: unverbundene Taxonomien bleiben nicht verfügbar.
        """
        import wn
        from wn import similarity

        values = {'path_similarity': 0.0, 'wup_similarity': 0.0, 'taxonomy_available': 0.0}
        for a in first['nodes']:
            for b in second['nodes']:
                if a.pos not in {'n', 'v'} or a.pos != b.pos:
                    continue
                key = tuple(sorted((a.id, b.id)))
                if key not in self.similarity_cache:
                    pair = None
                    try:
                        path = similarity.path(a, b, simulate_root=False)
                        if path:
                            pair = (path, similarity.wup(a, b, simulate_root=False))
                    except wn.Error:
                        pass  # Keine auswertbare Verbindung in dieser Taxonomie.
                    self.similarity_cache[key] = pair
                pair = self.similarity_cache[key]
                if pair is not None:
                    values['path_similarity'] = max(values['path_similarity'], pair[0])
                    values['wup_similarity'] = max(values['wup_similarity'], pair[1])
                    values['taxonomy_available'] = 1.0
        return values

    def relation_features(self, left, right, names):
        """Liefere Evidenzmatrizen, keine zusätzlichen Similarity-Scores.

        Binärwerte bedeuten Existenz bei mindestens einer Lesart; 0 kann auch
        fehlende Abdeckung bedeuten. Synsetanzahlen sind unskalierte Zählwerte.
        """
        if (not names or len(names) != len(set(names)) or set(names) - set(RELATION_FEATURES)):
            raise ValueError('unknown, empty or duplicate relation_features')
        result = {name: np.zeros((len(left), len(right))) for name in names}
        if not left or not right:
            return result
        profiles = {text: self._relation_profile(text) for text in set(left + right)}
        for i, reference in enumerate(left):
            for j, student in enumerate(right):
                a, b = profiles[reference], profiles[student]
                values = {
                    'pair_known': bool(a['synsets'] and b['synsets']),
                    'reference_synset_count': len(a['synsets']),
                    'student_synset_count': len(b['synsets']),
                    'reference_hypernym': bool(a['synsets'] & b['ancestors']),
                    'reference_hyponym': bool(a['ancestors'] & b['synsets']),
                    'antonym': bool(a['antonym_synsets'] & b['synsets']
                                    or b['antonym_synsets'] & a['synsets']
                                    or a['antonym_senses'] & b['senses']
                                    or b['antonym_senses'] & a['senses']),
                }
                if set(names) & {'path_similarity', 'wup_similarity', 'taxonomy_available'}:
                    values.update(self._taxonomy_similarity(a, b))
                for name in names:
                    result[name][i, j] = values[name]
        return result

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
