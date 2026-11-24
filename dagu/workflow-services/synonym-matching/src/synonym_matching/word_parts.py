"""Language-neutral label decomposition and part relations (AP-09).

Descriptive only: a relation names how two labels differ, it is never a score or a correspondence.
Parts come from Unicode letter/digit runs, case changes and letter/digit boundaries. Compound words
are split only at parts that occur as labels or label parts in the two compared models themselves;
there is no word list and no language-specific rule.
"""

import unicodedata

MINIMUM_PART = 3
RELATIONS = ("notation", "reordered", "head_form", "part_of_term", "abbreviation", "same_stem")


def _runs(label):
    """Split at non-alphanumerics, case changes (`aB`, `ABc` before `Bc`) and letter/digit boundaries."""
    text = unicodedata.normalize("NFC", label or "")
    runs, current, previous = [], "", None
    for index, char in enumerate(text):
        if not char.isalnum():
            if current:
                runs.append(current)
            current, previous = "", None
            continue
        following = text[index + 1] if index + 1 < len(text) else ""
        boundary = previous is not None and (
            (previous.islower() and char.isupper()) or (previous.isdigit() != char.isdigit())
            or (previous.isupper() and char.isupper() and following.islower()))
        if boundary and current:
            runs.append(current)
            current = ""
        current += char
        previous = char
    if current:
        runs.append(current)
    return [run.casefold() for run in runs]


def vocabulary(labels):
    """Parts that may split a compound: every label part of at least MINIMUM_PART letters."""
    return frozenset(part for label in labels for part in _runs(label) if len(part) >= MINIMUM_PART and part.isalpha())


def parts(label, words=frozenset()):
    """Label parts; a part splits once at the longest known word that forms its end (preferred) or start."""
    result = []
    for run in _runs(label):
        known = [word for word in words if word != run and len(run) - len(word) >= 2]
        tail = max((word for word in known if run.endswith(word)), key=len, default=None)
        head = max((word for word in known if run.startswith(word)), key=len, default=None)
        if tail:
            result += [run[:-len(tail)], tail]
        elif head:
            result += [head, run[len(head):]]
        else:
            result.append(run)
    return result


def _contains(longer, shorter):
    return next((start for start in range(len(longer) - len(shorter) + 1)
                 if longer[start:start + len(shorter)] == shorter), None)


def relation(reference_label, student_label, words=frozenset()):
    """How two labels relate part by part, or None when no part relation exists."""
    left, right = parts(reference_label, words), parts(student_label, words)
    if not left or not right:
        return None
    found = None
    if left == right:
        found = "notation" if reference_label != student_label else None
    elif sorted(left) == sorted(right):
        found = "reordered"
    else:
        shorter, longer = sorted((left, right), key=len)
        start = _contains(longer, shorter) if len(shorter) < len(longer) else None
        if start is not None:
            found = "head_form" if start + len(shorter) == len(longer) else "part_of_term"
        elif len(left) == len(right) and all(a == b or a.startswith(b) or b.startswith(a) for a, b in zip(left, right)):
            found = "abbreviation"
        elif left[0] == right[0] or left[-1] == right[-1]:
            found = "same_stem"
    if found is None:
        return None
    return {"relation": found, "referenceParts": left, "studentParts": right}
