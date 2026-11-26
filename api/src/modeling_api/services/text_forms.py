"""The prepared text each similarity method actually compared, mirroring synonym-matching's named forms."""

import re
import unicodedata

UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue"})


def _normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split())


STEPS = {
    "normalize": _normalize,
    "expand_abbreviations": lambda text: _normalize(re.sub(r"nr\.?(?=$|[\s_-])", " Nummer", text, flags=re.IGNORECASE)),
    "split_identifiers": lambda text: _normalize(re.sub(r"(?<=[a-zäöüß])(?=[A-ZÄÖÜ])", " ", text).replace("_", " ")),
    "casefold": str.casefold,
    "fold_umlauts": lambda text: text.translate(UMLAUTS),
    "compact": lambda text: re.sub(r"[\s_\-/]+", "", text),
}
EXPANDED = ("normalize", "expand_abbreviations", "split_identifiers")
# shortcut: forms are fixed per method name; a custom `semantics.preprocessing` override is not reflected, store the forms in the candidates artifact then.
FORMS = {"damerau_canonical": EXPANDED + ("casefold", "fold_umlauts", "compact"),
         "levenshtein_canonical": EXPANDED + ("casefold", "fold_umlauts", "compact"),
         "multilingual_expanded": EXPANDED}


def prepared(method: str, text: str) -> str | None:
    steps = FORMS.get(method)
    if steps is None:
        return None
    for step in steps:
        text = STEPS[step](text)
    return text
