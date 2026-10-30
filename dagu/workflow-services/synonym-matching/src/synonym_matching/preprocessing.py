"""Composable text transformations; pipelines apply functions in explicit order."""

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
    # Deliberately includes negations: an ablation, not a recommended default.
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


def split_compounds(text, language=None):
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
            if left not in words:
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


# Names are also used in reproducible JSON experiment configurations.
STEPS = {
    'normalize': normalize,
    'split_identifiers': split_identifiers,
    'lemmatize': lemmatize,
    'lowercase': lowercase,
    'stem': stem,
    'remove_stopwords': remove_stopwords,
    'split_compounds': split_compounds,
}


def apply_pipeline(text, steps, language=None):
    """Apply any sequence of functions with signature (text, language=None)."""
    for step in steps:
        text = step(text, language=language)
    return text


def build_pipeline(config=None):
    """Accept ordered function/name lists or the existing Boolean configuration."""
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
    """Small cache around a function pipeline; no transformation logic here."""
    def __init__(self, config=None):
        """Erstelle die geordnete Verarbeitungskette und einen leeren Cache."""
        self.steps = build_pipeline(config)
        self.cache = {}

    def process(self, text, language=None):
        """Verarbeite jeden Text pro Sprache nur einmal."""
        key = (text, language)
        if key not in self.cache:
            self.cache[key] = apply_pipeline(text, self.steps, language)
        return self.cache[key]
