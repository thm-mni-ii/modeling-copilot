"""Conservative normalization copied from the method reference."""

import unicodedata


def normalize(text):
    return " ".join(unicodedata.normalize("NFC", text).split())
