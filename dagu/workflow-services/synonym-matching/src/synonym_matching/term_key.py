"""Language-neutral glossary term key; the matcher image copies this file and the API mirrors it."""

import unicodedata

TERM_NORMALIZATION = "nfc-casefold-space-v1"


def term_key(text):
    """NFC, collapsed whitespace, casefold, without trailing `. : , ;`."""
    collapsed = " ".join(unicodedata.normalize("NFC", text).split())
    return unicodedata.normalize("NFC", collapsed.casefold()).rstrip(" .:,;")
