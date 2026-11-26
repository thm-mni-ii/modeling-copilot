#!/usr/bin/env python3
"""Compare benchmark run results with the generated truth.

Per reference object: `certain` (uniquely supported with the true counterpart), `hint` (hint with the
true counterpart), `partial` (pair decision `partial`), `wrong` (certain with another object),
`wrong_hint` or `missed`. Objects whose counterpart was removed or only structurally recognisable
(wrong or shuffled labels) are reported separately; a certain pair for them is `structural` when it
hits the same object and `wrong` otherwise.

Usage: python evaluate.py CASES_DIR RESULTS_DIR [--markdown REPORT.md] [--summary SUMMARY.json]

`--summary` writes per case and reference object the outcome and counterpart, the input of compare.py.
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

LANGUAGE = {"uml-order-management": "UML (en)", "serm-laboratory": "SERM (de)", "serm-game-studio": "SERM (de)", "erm-laboratory": "ERM (de)"}
OUTCOMES = ("certain", "hint", "partial", "missed", "wrong", "wrong_hint")


def assess(case, result):
    truth, reference_nodes = case["truth"], result["nodes"]["reference_1"]
    certain = {row["referenceId"]: row for row in result["identity"] if row["status"] == "uniquely_supported"}
    hints = {row["referenceId"]: row["studentId"] for row in result["hints"]}
    partial = {(row["referenceId"], row["studentId"]) for row in result["pairDecisions"] if row["decision"] == "partial"}
    rows = []
    for identity, item in truth.items():
        if reference_nodes.get(identity, {}).get("kind") != "modelElement":
            continue
        expected, category, hit = item["expected"], item["category"], certain.get(identity)
        if hit is not None:
            outcome = ("certain" if hit["studentId"] == expected else
                       "structural" if expected is None and hit["studentId"] == identity and category in ("wrong_label", "shuffled") else "wrong")
        elif identity in hints:
            outcome = ("hint" if hints[identity] == expected else
                       "structural_hint" if expected is None and hints[identity] == identity and category in ("wrong_label", "shuffled") else "wrong_hint")
        elif expected is not None and (identity, expected) in partial:
            outcome = "partial"
        else:
            outcome = "missed" if expected is not None else "absent_ok"
        rows.append({"referenceId": identity, "label": item["label"], "submissionLabel": item["submissionLabel"],
                     "category": category, "outcome": outcome, "anchors": hit["anchors"] if hit else [],
                     "matchedTo": hit["studentId"] if hit else hints.get(identity)})
    extra = set(case["extra"]) if case["case"] != "foreign_solution" else set()
    decoys = [row for row in result["identity"] if row["status"] == "uniquely_supported" and row["studentId"] in extra]
    connections = [identity for identity, node in reference_nodes.items() if node["kind"] == "connection"]
    connection_hits = sum(certain.get(identity, {}).get("studentId") == identity for identity in connections)
    return rows, decoys, connection_hits, len(connections)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    cases_dir, results_dir = Path(sys.argv[1]), Path(sys.argv[2])
    report = Path(sys.argv[sys.argv.index("--markdown") + 1]) if "--markdown" in sys.argv else None
    summary_path = Path(sys.argv[sys.argv.index("--summary") + 1]) if "--summary" in sys.argv else None
    summary = {}
    per_case, by_category, findings, errors = [], defaultdict(Counter), defaultdict(list), []
    scores = defaultdict(list)  # (language, category) -> [(spelling, meaning)] of the true pairs
    for path in sorted(results_dir.glob("*__*.json")):
        result = json.loads(path.read_text(encoding="utf-8"))
        case = json.loads((cases_dir / path.name).read_text(encoding="utf-8"))
        if result["status"] != "ok":
            errors.append((path.stem, result["error"][-300:]))
            continue
        rows, decoys, connection_hits, connection_total = assess(case, result)
        certain = {row["referenceId"]: row["studentId"] for row in result["identity"] if row["status"] == "uniquely_supported"}
        summary[path.stem] = {
            "elements": {row["referenceId"]: {"outcome": row["outcome"], "matchedTo": row["matchedTo"], "category": row["category"]} for row in rows},
            "connections": {identity: certain.get(identity) for identity, node in result["nodes"]["reference_1"].items() if node["kind"] == "connection"},
            "hints": sorted([row["referenceId"], row["studentId"]] for row in result["hints"]),
            "recognition": [result["recognition"]["overall"]["recognized"], result["recognition"]["overall"]["expected"]]}
        language = LANGUAGE.get(case["reference"], case["reference"])
        outcomes = Counter(row["outcome"] for row in rows)
        matchable = sum(row["category"] not in ("removed", "wrong_label", "shuffled") for row in rows)
        overall = result["recognition"]["overall"]
        per_case.append({"reference": case["reference"], "case": case["case"], "matchable": matchable, **outcomes,
                         "decoys": len(decoys), "connections": f"{connection_hits}/{connection_total}",
                         "recognition": f"{overall['recognized']}/{overall['expected']}", "hintsShown": len(result["learnerHints"])})
        for row in rows:
            by_category[(language, row["category"])][row["outcome"]] += 1
            value = (result.get("trueScores") or {}).get(row["referenceId"])
            if value and row["category"] in ("notation", "typo", "abbreviation", "synonym", "translation", "short_form", "moved"):
                scores[(language, row["category"])].append((value.get("damerau_canonical"), value.get("multilingual_expanded")))
            if row["outcome"] in ("wrong", "wrong_hint", "structural") or row["category"] in ("abbreviation", "translation", "synonym", "short_form") and row["outcome"] != "certain":
                findings[(language, row["category"], row["outcome"])].append(f"{row['label']} → {row['submissionLabel']}" + (f" (an {row['matchedTo']})" if row["outcome"].startswith("wrong") else ""))
        for row in decoys:
            findings[(language, "decoy", "wrong")].append(f"{row['referenceId']} ← {row['studentId']}")
    lines = ["## Ergebnis je Testfall", "", "| Referenz | Fall | zuordenbar | sicher | Hinweis | teilweise | verpasst | falsch | strukturell | Köder falsch | Verbindungen | Quote | Hinweise |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for row in per_case:
        lines.append(f"| {row['reference']} | {row['case']} | {row['matchable']} | {row.get('certain', 0)} | {row.get('hint', 0)} | {row.get('partial', 0)} | "
                     f"{row.get('missed', 0)} | {row.get('wrong', 0) + row.get('wrong_hint', 0)} | {row.get('structural', 0) + row.get('structural_hint', 0)} | {row['decoys']} | {row['connections']} | {row['recognition']} | {row['hintsShown']} |")
    lines += ["", "## Ergebnis je Sprache und Abweichungsart", "", "| Sprache | Art | Objekte | sicher | Hinweis | teilweise | verpasst | falsch | strukturell | korrekt abwesend |", "|---|---|---|---|---|---|---|---|---|---|"]
    for (language, category), counts in sorted(by_category.items()):
        total = sum(counts.values())
        lines.append(f"| {language} | {category} | {total} | {counts['certain']} | {counts['hint']} | {counts['partial']} | {counts['missed']} | "
                     f"{counts['wrong'] + counts['wrong_hint']} | {counts['structural'] + counts['structural_hint']} | {counts['absent_ok']} |")
    lines += ["", "## Textwerte der Sollpaare", "",
              "Anteil der Sollpaare je Schwelle: Schreibvariante `damerau_canonical` ≥ 0,85, Bedeutung `multilingual_expanded` ≥ 0,85, Graubereich ≥ 0,70.", "",
              "| Sprache | Art | Paare | Schreibvariante ≥ 0,85 | Bedeutung ≥ 0,85 | eine Stufe erreicht | Graubereich 0,70–0,85 | Median Bedeutung |", "|---|---|---|---|---|---|---|---|"]
    for (language, category), values in sorted(scores.items()):
        spelling = [a for a, _ in values if a is not None]
        meaning = sorted(b for _, b in values if b is not None)
        tier = sum((a or 0) >= 0.85 or (b or 0) >= 0.85 for a, b in values)
        grey = sum((a or 0) < 0.85 and 0.70 <= (b or 0) < 0.85 for a, b in values)
        median = meaning[len(meaning) // 2] if meaning else None
        lines.append(f"| {language} | {category} | {len(values)} | {sum(a >= 0.85 for a in spelling)} | {sum(b >= 0.85 for b in meaning)} | {tier} | {grey} | "
                     f"{median:.2f} |" if median is not None else f"| {language} | {category} | {len(values)} | – | – | {tier} | {grey} | – |")
    lines += ["", "## Einzelbefunde", ""]
    for (language, category, outcome), items in sorted(findings.items()):
        sample = sorted(Counter(items).items(), key=lambda pair: -pair[1])[:12]
        lines.append(f"- **{language} · {category} · {outcome}** ({len(items)}): " + "; ".join(f"{text} ×{count}" if count > 1 else text for text, count in sample))
    if errors:
        lines += ["", "## Fehlgeschlagene Läufe", ""] + [f"- {name}: `{error}`" for name, error in errors]
    if summary_path:
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    text = "\n".join(lines)
    if report:
        report.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
