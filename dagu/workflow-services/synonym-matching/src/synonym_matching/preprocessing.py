"""Composable text transformations; pipelines apply functions in explicit order."""
import re
import unicodedata
from functools import lru_cache


def normalize(text, language=None):
    return " ".join(unicodedata.normalize("NFC", text).split())


def lowercase(text, language=None):
    return text.lower()


def split_identifiers(text, language=None):
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text).replace("_", " ")


@lru_cache(maxsize=2)
def _language_model(language):
    import spacy
    model = {"de": "de_core_news_sm", "en": "en_core_web_sm"}[language]
    return spacy.load(model, disable=["parser", "ner"])


def lemmatize(text, language=None):
    if not text.strip():
        return text
    if language not in {"de", "en"}:
        raise ValueError("lemmatization requires explicit language 'de' or 'en'")
    return " ".join(token.lemma_ for token in _language_model(language)(text))


# Names are also used in reproducible JSON experiment configurations.
STEPS = {function.__name__: function for function in
         (normalize, split_identifiers, lemmatize, lowercase)}


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
        self.steps = build_pipeline(config)
        self.cache = {}

    def process(self, text, language=None):
        key = (text, language)
        if key not in self.cache:
            self.cache[key] = apply_pipeline(text, self.steps, language)
        return self.cache[key]
