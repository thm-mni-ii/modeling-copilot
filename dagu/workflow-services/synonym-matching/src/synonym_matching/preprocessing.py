"""Registered text preparation steps; each step maps one label text to another."""

import re
import unicodedata


def normalize(text):
    return " ".join(unicodedata.normalize("NFC", text).split())


def casefold(text):
    return text.casefold()


def split_identifiers(text):
    """Separate camelCase boundaries and underscores into words."""
    return normalize(re.sub(r"(?<=[a-zäöüß])(?=[A-ZÄÖÜ])", " ", text).replace("_", " "))


UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue"})


def fold_umlauts(text):
    """Write umlauts as their two-letter transcription; applied to both sides, `Geräte` equals `Geraete`."""
    return text.translate(UMLAUTS)


def compact(text):
    """Drop word separators so split, joined and hyphenated spellings compare equal (`Labor-Raum`, `Laborraum`)."""
    return re.sub(r"[\s_\-/]+", "", text)


def expand_abbreviations(text):
    """Spell out the number abbreviation `Nr`/`Nr.` at a word end, also inside `GebäudeNr.`."""
    # shortcut: only the German `Nr.` without a language check; extend once labels carry a language.
    return normalize(re.sub(r"nr\.?(?=$|[\s_-])", " Nummer", text, flags=re.IGNORECASE))
