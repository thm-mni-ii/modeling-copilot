"""Lokale Synonymlexika ohne Netzwerkzugriff während des Matchings."""

from pathlib import Path

from .preprocessing import normalize

DATA_DIR = Path(__file__).resolve().parents[2] / '.cache' / 'lexicons'
RELATION_FEATURES = (
    'pair_known', 'reference_synset_count', 'student_synset_count',
    'reference_hypernym', 'reference_hyponym', 'antonym',
    'path_similarity', 'wup_similarity', 'taxonomy_available',
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
        self.form_cache = {}

    def _load(self):
        """Öffne nur lokale Daten; Englisch bekommt zusätzlich Morphy."""
        import wn

        message = (f'{type(self).__name__} missing ({self.version}): '
                   'run PYTHONPATH=src python scripts/download_lexicons.py')
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
            # Der wn-Index liefert Kandidaten; OdeNet._forms prüft anschließend
            # die tatsächliche Schreibweise, ohne Akzente/Umlaute anzugleichen.
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



class OdeNet(WordNet):
    """Nutze denselben lokalen Zugriff für Deutsch, ohne englische Morphologie."""

    version = 'odenet:1.4'
    language = 'de'

    def _key(self, text):
        """Originalschreibung für die erste Suche erhalten; nur NFC/Leerraum ändern."""
        return normalize(text)

    def _forms(self, text):
        """Nur belegte Formen gleicher Schreibweise (bis auf Großschreibung).

        wn kann bei normalisierter Suche auch Zahlung/Zählung zusammen liefern.
        Die tatsächlichen Wortformen filtern solche Kandidaten aus. Derselbe
        Filter gilt für Synsets und wortbezogene Antonymrelationen.
        """
        if text not in self.form_cache:
            expected = key(text)  # lower(), kein Akzententfernen und kein ß→ss.
            self.form_cache[text] = {None: {
                form for word in self.reader.words(text) for form in word.forms()
                if key(form) == expected
            }}
        return self.form_cache[text]


class LexiconMatcher:
    """OdeNet zuerst, danach Lingua/WordNet; englische Synsets verbinden Quellen.

    Nur die Originalbezeichnung wird zur Spracherkennung verwendet. Explizite
    language-Felder sind weder erforderlich noch Entscheidungsgrundlage.
    """

    def __init__(self, path=None, minimum_relative_distance=.2):
        self.backends = {'de': OdeNet(path), 'en': WordNet(path)}
        self.minimum_relative_distance = minimum_relative_distance
        self.detector = None
        self.languages, self.linked = {}, {}

    def detect(self, text):
        """Einmal pro eindeutigem Originaltext zwischen DE und EN entscheiden."""
        if text not in self.languages:
            if self.detector is None:
                from lingua import Language, LanguageDetectorBuilder
                self.detector = (LanguageDetectorBuilder.from_languages(Language.GERMAN, Language.ENGLISH)
                    .with_minimum_relative_distance(self.minimum_relative_distance).build())
            result = self.detector.detect_language_of(text) if text.strip() else None
            self.languages[text] = result.iso_code_639_1.name.lower() if result else None
        return self.languages[text]

    def route(self, original, text, mode):
        """Ein OdeNet-Eintrag wählt DE, ohne daraus die gemeinte Lesart abzuleiten."""
        if mode == 'odenet' or self.backends['de'].lookup(text):
            return 'de'
        return 'en' if self.detect(original) == 'en' else None

    def profile(self, text, language, *, linked=False):
        """Verknüpfte Profile ausschließlich aus nativen wn-Relationen aufbauen."""
        if language is None:
            return {'synsets': frozenset(), 'nodes': [], 'ancestors': set(),
                    'antonym_synsets': set(), 'senses': set(), 'antonym_senses': set()}
        source = self.backends[language]
        original = source._relation_profile(text)
        if not linked or language == 'en':
            return original
        if text not in self.linked:
            english = self.backends['en']
            if english.reader is None:
                english._load()
            ids = source.translate(text)
            nodes = [english.reader.synset(identifier) for identifier in ids]
            senses = {sense.id: sense for identifier in original['senses']
                      for sense in source.reader.sense(identifier).translate(lexicon=english.version)}
            self.linked[text] = {'synsets': ids, 'nodes': nodes,
                'ancestors': {a.id for node in nodes for a in node.closure('hypernym', 'instance_hypernym')
                              if a.id != node.id},
                'antonym_synsets': {a.id for node in nodes for a in node.relations('antonym').get('antonym', [])},
                'senses': set(senses), 'antonym_senses': {a.id for sense in senses.values()
                    for a in sense.relations('antonym').get('antonym', [])}}
        return self.linked[text]

    def pair_features(self, first, second, language_a, language_b, *, mode='odenet_linked'):
        """Numerische Abdeckung, Relationen und diagnostische Taxonomiewerte."""
        original_a, original_b = self.profile(first, language_a), self.profile(second, language_b)
        cross = bool(language_a and language_b and language_a != language_b)
        comparable = bool(language_a and language_b and (not cross or mode == 'odenet_linked'))
        a, b = original_a, original_b
        if cross and comparable:
            a, b = self.profile(first, language_a, linked=True), self.profile(second, language_b, linked=True)
        known = bool(comparable and a['synsets'] and b['synsets'])
        values = {'reference_known': float(bool(original_a['synsets'])),
            'student_known': float(bool(original_b['synsets'])), 'pair_known': float(known),
            'reference_synset_count': float(max(len(original_a['synsets']), len(a['synsets']))),
            'student_synset_count': float(max(len(original_b['synsets']), len(b['synsets']))),
            'reference_linked': float(bool(comparable and a['synsets'])),
            'student_linked': float(bool(comparable and b['synsets'])), 'cross_language': float(cross),
            'shared_synset': float(known and bool(a['synsets'] & b['synsets'])),
            'reference_hypernym': float(known and bool(a['synsets'] & b['ancestors'])),
            'reference_hyponym': float(known and bool(a['ancestors'] & b['synsets'])),
            'antonym': float(known and bool(a['antonym_synsets'] & b['synsets'] or b['antonym_synsets'] & a['synsets']
                or a['antonym_senses'] & b['senses'] or b['antonym_senses'] & a['senses'])),
            'path_similarity': 0., 'wup_similarity': 0., 'taxonomy_available': 0.}
        if known:
            values.update(self.backends['en']._taxonomy_similarity(a, b))
        return values
