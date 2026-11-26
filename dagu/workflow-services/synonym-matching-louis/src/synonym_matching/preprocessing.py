"""Die wenigen Textformen der ausgewählten Pipeline, ohne Sprachmetadaten."""

import re
import unicodedata

ABBREVIATIONS = {'Anz.': 'Anzahl', 'Bez.': 'Bezeichnung',
                 'Beschr.': 'Beschreibung', 'PLZ': 'Postleitzahl'}
UMLAUTS = str.maketrans({'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue'})


def normalize(text):
    """Unicode vereinheitlichen und Leerraum zusammenfassen."""
    return ' '.join(unicodedata.normalize('NFC', text).split())


def expand_modeling_abbreviations(text):
    """Vereinbarte deutsche Modellierungskürzel an Wort-/CamelCase-Grenzen lösen.

    Deutsch ist der Anwendungsschwerpunkt, kein aus einem Testlabel abgelesener
    Sprachwert. Keine Expansion beliebiger studentischer Kurzformen.
    """
    for short, full in ABBREVIATIONS.items():
        def replace(match):
            start, end = match.span()
            previous = text[start - 1] if start else ''
            following = text[end] if end < len(text) else ''
            camel = previous.islower() and text[start].isupper()
            if (previous.isalnum() and not camel) or following.isalnum():
                return match.group()
            return (' ' if camel else '') + full
        text = re.sub(re.escape(short), replace, text, flags=re.IGNORECASE)
    return normalize(text)


def expanded(text):
    """Nr. lösen, danach Identifier trennen; Großschreibung für Jina erhalten."""
    text = expand_modeling_abbreviations(text)
    text = normalize(re.sub(r'nr\.?(?=$|[\s_-])', ' Nummer', text, flags=re.IGNORECASE))
    return normalize(re.sub(r'(?<=[a-zäöüß])(?=[A-ZÄÖÜ])', ' ', text).replace('_', ' '))


def canonical(text):
    """Produktive Stringform: expandieren, casefold, Umlaute und Trenner angleichen."""
    return re.sub(r'[\s_\-/]+', '', expanded(text).casefold().translate(UMLAUTS))


def text_veto(first, second):
    """Produktive Textguards: Zahlenkonflikt bzw. unterschiedlicher Wortanfang."""
    left, right = re.findall(r'\d+', first), re.findall(r'\d+', second)
    if left and right and left != right:
        return 'digit_mismatch'
    def start(text):
        return re.sub(r'[\W_]+', '', text.casefold().translate(UMLAUTS))[:2]
    return 'start_mismatch' if start(first) != start(second) else None
