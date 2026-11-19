"""Measure the matcher's Levenshtein threshold rule against the gold label-variant corpus.

Recognition mirrors the graph matcher: an NFC/whitespace-identical label is an exact
anchor; otherwise the Levenshtein similarity must reach the threshold. Only
`equivalent` and `not_equivalent` cases are scored; `partial` and `context` cases are
reported as acceptance rates because their verdict is a didactic decision.
"""

import argparse
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from synonym_matching.methods.levenshtein import compute as levenshtein  # noqa: E402
from synonym_matching.preprocessing import normalize  # noqa: E402

CORPUS = Path(__file__).resolve().parents[1] / "calibration" / "label-variants.json"
EXPECTED = ("equivalent", "not_equivalent", "partial", "context")
PREPROCESSING = {"normalize": normalize, "normalize+casefold": lambda text: normalize(text).casefold()}
THRESHOLDS = tuple(round(0.5 + step * 0.05, 2) for step in range(10))


def load_corpus(path=CORPUS):
    corpus = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_corpus(corpus)
    return corpus


def validate_corpus(corpus, minimum_per_category=6):
    if corpus.get("schema") != "label-variant-corpus/v1":
        raise ValueError("unsupported corpus schema")
    categories, cases = corpus["categories"], corpus["cases"]
    seen, counts = set(), dict.fromkeys(categories, 0)
    for case in cases:
        identity, category = case["id"], case["category"]
        if identity in seen:
            raise ValueError(f"duplicate case ID: {identity}")
        seen.add(identity)
        if category not in categories or not re.fullmatch(rf"{category}-\d{{2}}", identity):
            raise ValueError(f"case ID does not match a declared category: {identity}")
        if case["expected"] not in EXPECTED:
            raise ValueError(f"unknown expected verdict: {identity}")
        if not all(isinstance(case[key], str) and case[key].strip() for key in ("reference", "variant")):
            raise ValueError(f"reference and variant labels are required: {identity}")
        counts[category] += 1
    thin = sorted(category for category, count in counts.items() if count < minimum_per_category)
    if thin:
        raise ValueError(f"categories below {minimum_per_category} cases: {', '.join(thin)}")
    return counts


def score_cases(cases, preprocessing="normalize"):
    """Attach the service's Levenshtein score and the matcher's exact-anchor flag."""
    prepare = PREPROCESSING[preprocessing]
    scored = []
    for case in cases:
        score = float(levenshtein([prepare(case["reference"])], [prepare(case["variant"])])[0, 0])
        scored.append({**case, "score": score, "exact": normalize(case["reference"]) == normalize(case["variant"])})
    return scored


def recognized(case, threshold):
    return case["exact"] or case["score"] >= threshold


def evaluate(scored, threshold):
    totals = {"tp": 0, "fn": 0, "fp": 0, "tn": 0}
    categories = {}
    for case in scored:
        row = categories.setdefault(case["category"], {"equivalent": [0, 0], "not_equivalent": [0, 0], "open": [0, 0]})
        hit = recognized(case, threshold)
        bucket = case["expected"] if case["expected"] in ("equivalent", "not_equivalent") else "open"
        row[bucket][0] += hit
        row[bucket][1] += 1
        if case["expected"] == "equivalent":
            totals["tp" if hit else "fn"] += 1
        elif case["expected"] == "not_equivalent":
            totals["fp" if hit else "tn"] += 1
    precision = totals["tp"] / (totals["tp"] + totals["fp"]) if totals["tp"] + totals["fp"] else None
    recall = totals["tp"] / (totals["tp"] + totals["fn"]) if totals["tp"] + totals["fn"] else None
    f1 = 2 * precision * recall / (precision + recall) if precision and recall else None
    return {"threshold": threshold, **totals, "precision": precision, "recall": recall, "f1": f1, "categories": categories}


def _rate(pair):
    return f"{pair[0]}/{pair[1]}" if pair[1] else "–"


def _number(value):
    return "–" if value is None else f"{value:.2f}"


def render_report(corpus, thresholds=(0.7, 0.8, 0.9), detail=None):
    lines = [f"# Levenshtein-Kalibrierung ({len(corpus['cases'])} Fälle)", "",
             "Erkannt = exakter Anker (NFC/Whitespace) oder Score ≥ Schwelle. "
             "Bewertet werden nur `equivalent` und `not_equivalent`.", ""]
    for name in PREPROCESSING:
        scored = score_cases(corpus["cases"], name)
        lines += [f"## Schwellen-Sweep: {name}", "", "| Schwelle | TP | FN | FP | TN | Precision | Recall | F1 |",
                  "|---|---|---|---|---|---|---|---|"]
        for threshold in THRESHOLDS:
            result = evaluate(scored, threshold)
            lines.append(f"| {threshold:.2f} | {result['tp']} | {result['fn']} | {result['fp']} | {result['tn']} | "
                         f"{_number(result['precision'])} | {_number(result['recall'])} | {_number(result['f1'])} |")
        lines += ["", f"## Kategorien: {name}", "",
                  "Je Schwelle: erkannte Äquivalente · Fehltreffer bei Negativen · angenommene offene Fälle (partial/context).", "",
                  "| ID | Kategorie | " + " | ".join(f"{threshold:.2f}" for threshold in thresholds) + " |",
                  "|---|---|" + "---|" * len(thresholds)]
        results = [evaluate(scored, threshold) for threshold in thresholds]
        for category, label in corpus["categories"].items():
            cells = []
            for result in results:
                row = result["categories"].get(category, {"equivalent": [0, 0], "not_equivalent": [0, 0], "open": [0, 0]})
                cells.append(f"✓ {_rate(row['equivalent'])} · ✗ {_rate(row['not_equivalent'])} · ◐ {_rate(row['open'])}")
            lines.append(f"| {category} | {label} | " + " | ".join(cells) + " |")
        lines.append("")
        if detail is not None:
            wrong = [case for case in scored if case["expected"] in ("equivalent", "not_equivalent")
                     and recognized(case, detail) != (case["expected"] == "equivalent")]
            lines += [f"### Fehlentscheidungen bei {detail:.2f} ({name})", "", "| ID | Referenz | Variante | Score | Soll |",
                      "|---|---|---|---|---|"]
            lines += [f"| {case['id']} | {case['reference']} | {case['variant']} | {case['score']:.3f} | {case['expected']} |"
                      for case in wrong]
            lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=CORPUS)
    parser.add_argument("--thresholds", default="0.7,0.8,0.9", help="Comma-separated thresholds for the category table.")
    parser.add_argument("--detail", type=float, help="List wrong decisions at this threshold.")
    args = parser.parse_args()
    thresholds = tuple(float(value) for value in args.thresholds.split(","))
    print(render_report(load_corpus(args.corpus), thresholds, args.detail))


if __name__ == "__main__":
    main()
