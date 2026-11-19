"""Kombinierbare Textvorbereitung mit ausdrücklich festgelegter Reihenfolge."""

import re
import unicodedata
from functools import lru_cache


def normalize(text, language=None):
    """Normalisiere Unicode und fasse aufeinanderfolgenden Leerraum zusammen."""
    return " ".join(unicodedata.normalize("NFC", text).split())


def lowercase(text, language=None):
    """Wandle den Text in Kleinbuchstaben um."""
    return text.lower()


def split_identifiers(text, language=None):
    """Trenne camelCase und Unterstriche in einzelne Wörter."""
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text).replace("_", " ")


def expand_abbreviations(text, language=None):
    """Löse deutsches Nr./Nr am Wortende auf, auch in GebäudeNr.

    Bewusst kleine Regel: Andere Abkürzungen und Sprachen bleiben unverändert.
    """
    if language != 'de':
        return text
    return normalize(re.sub(r'nr\.?(?=$|[\s_-])', ' Nummer', text, flags=re.IGNORECASE))


@lru_cache(maxsize=2)
def _language_model(language):
    """Lade das spaCy-Modell einmal pro Sprache."""
    import spacy
    model = {"de": "de_core_news_sm", "en": "en_core_web_sm"}[language]
    return spacy.load(model, disable=["parser", "ner"])


def lemmatize(text, language=None):
    """Ersetze Wörter durch ihre sprachabhängige Grundform."""
    if not text.strip():
        return text
    if language not in {"de", "en"}:
        raise ValueError("lemmatization requires explicit language 'de' or 'en'")
    return " ".join(token.lemma_ for token in _language_model(language)(text))


@lru_cache(maxsize=2)
def _stemmer(language):
    """Erzeuge den Snowball-Stemmer für Deutsch oder Englisch."""
    if language not in {"de", "en"}:
        raise ValueError("stemming requires explicit de/en language")
    from nltk.stem.snowball import SnowballStemmer
    return SnowballStemmer({"de": "german", "en": "english"}[language])


def stem(text, language=None):
    """Reduziere Wörter auf ihren Stamm; benötigt keinen Korpusdownload."""
    if not text.strip():
        return text
    return " ".join(_stemmer(language).stem(token) for token in text.split())


@lru_cache(maxsize=2)
def _tokenizer(language):
    """Erzeuge einen spaCy-Tokenizer mit der passenden Stopwortliste."""
    if language not in {"de", "en"}:
        raise ValueError("stopword removal requires explicit de/en language")
    import spacy
    return spacy.blank(language)


def remove_stopwords(text, language=None):
    """Entferne Stopwörter, möglicherweise auch bedeutungstragende Negation."""
    if not text.strip():
        return text
    nlp = _tokenizer(language)
    # Enthält bewusst Negationen: für Ablationsstudien, nicht als Standard.
    kept_tokens = []
    for token in nlp(text):
        if token.is_space or token.text.lower() in nlp.Defaults.stop_words:
            continue
        kept_tokens.append(token.text)
    return " ".join(kept_tokens)


@lru_cache(maxsize=1)
def _compound_words():
    """Nutze das vorhandene deutsche Lexikon statt testfallspezifischer Regeln."""
    from .lexicons import OpenThesaurus

    lexicon = OpenThesaurus()
    lexicon._load()
    return {word for word in lexicon.groups if word.isalpha() and len(word) >= 3}


def split_compounds(text, language=None, *, plural_forms=False):
    """Zerlege deutsche Wörter heuristisch in zwei bekannte Lexikonwörter.

    Längster linker Bestandteil zuerst; mögliche Fugenelemente werden entfernt.
    Das ist eine Ablation, keine vollständige linguistische Kompositazerlegung.
    Andere Sprachen und nicht zerlegbare Wörter bleiben unverändert.
    """
    if not text.strip() or language != 'de':
        return text
    words = _compound_words()
    result = []
    for token in text.split():
        lowered = token.lower()
        replacement = None
        for cut in range(len(lowered) - 3, 2, -1):
            left = lowered[:cut]
            # Nur die neue Labelzerlegung erlaubt diese einfache Pluralheuristik:
            # Geräte ist als linker Teil bekannt, wenn Gerät im Lexikon steht.
            known_left = left in words or (
                plural_forms and left.endswith('e') and left[:-1] in words
            )
            if not known_left:
                continue
            remainder = lowered[cut:]
            for linking in ('', 's', 'es', 'n', 'en', 'er'):
                if not remainder.startswith(linking):
                    continue
                right = remainder[len(linking):]
                if right in words:
                    replacement = left + ' ' + right
                    break
            if replacement:
                break
        result.append(replacement or token)
    return ' '.join(result)


def split_label_parts(text, language=None):
    """Kombiniere Abkürzungen, Identifier und die vorhandene Kompositazerlegung.

    Optionaler deutscher Forschungsschritt, keine vollständige Sprachanalyse.
    Die bisherigen Schritte und ihre Standardausgaben bleiben erhalten.
    """
    if not text.strip() or language != 'de':
        return text
    text = expand_abbreviations(text, language)
    text = split_identifiers(text, language)
    return split_compounds(text, language, plural_forms=True)


# Diese Namen werden auch in gespeicherten Experimentkonfigurationen verwendet.
STEPS = {
    'normalize': normalize,
    'split_identifiers': split_identifiers,
    'lemmatize': lemmatize,
    'lowercase': lowercase,
    'stem': stem,
    'remove_stopwords': remove_stopwords,
    'split_compounds': split_compounds,
    'expand_abbreviations': expand_abbreviations,
    'split_label_parts': split_label_parts,
}
# Kein Eintrag in STEPS: Übersetzen braucht Modell und Stapel, deshalb handelt es der Preprocessor.
TRANSLATE = 'translate'


def apply_pipeline(text, steps, language=None):
    """Wende Funktionen der Form (text, language=None) der Reihe nach an."""
    for step in steps:
        text = step(text, language=language)
    return text


def build_pipeline(config=None):
    """Akzeptiere geordnete Funktionen/Namen oder die bisherige Bool-Konfiguration."""
    if config is None:
        return [normalize]
    if isinstance(config, (list, tuple)):
        result = []
        for step in config:
            if isinstance(step, str) and step in STEPS:
                result.append(STEPS[step])
            elif callable(step):
                result.append(step)
            else:
                raise ValueError(f"unknown preprocessing step: {step}")
        return result
    if not isinstance(config, dict):
        raise ValueError("preprocessing must be a step list or configuration object")
    if set(config) - STEPS.keys() or any(type(v) is not bool for v in config.values()):
        raise ValueError(f"invalid preprocessing configuration: {config}")
    return [step for name, step in STEPS.items() if config.get(name, name == "normalize")]


class Preprocessor:
    """Verwaltet eine Verarbeitungskette und ihren Cache, ohne eigene Textumformung.

    In einer Schrittliste darf einmal 'translate' stehen: Schritte davor laufen auf
    dem Originaltext, dann wird gebündelt DE→EN übersetzt, Schritte danach laufen
    auf dem englischen Text (Sprache 'en'). Dafür braucht es einen Übersetzer.
    """
    def __init__(self, config=None, translator=None):
        """Erstelle die geordnete Verarbeitungskette und leere Caches."""
        steps = list(config) if isinstance(config, (list, tuple)) else None
        if steps is not None and steps.count(TRANSLATE) > 1:
            raise ValueError("translate may appear only once")
        self.after = None
        if steps is not None and TRANSLATE in steps:
            position = steps.index(TRANSLATE)
            self.steps = build_pipeline(steps[:position])
            self.after = build_pipeline(steps[position + 1:])
        else:
            self.steps = build_pipeline(config)
        self.translator = translator
        self.cache = {}
        self.after_cache = {}

    def process(self, text, language=None):
        """Verarbeite jeden Text pro Sprache nur einmal."""
        if self.after is not None:
            return self.process_many([text], [language])[0][0]
        return self._apply(self.steps, self.cache, text, language)

    def process_many(self, texts, languages):
        """Verarbeite viele Labels; liefere Texte und die Sprachen nach der Verarbeitung."""
        texts = [self._apply(self.steps, self.cache, text, language)
                 for text, language in zip(texts, languages)]
        if self.after is None:
            return texts, list(languages)
        if self.translator is None:
            raise ValueError("the translate step needs a translator")
        translated = self.translator.translate(texts, languages)
        return ([self._apply(self.after, self.after_cache, text, 'en') for text in translated],
                ['en'] * len(translated))

    @staticmethod
    def _apply(steps, cache, text, language):
        key = (text, language)
        if key not in cache:
            cache[key] = apply_pipeline(text, steps, language)
        return cache[key]
