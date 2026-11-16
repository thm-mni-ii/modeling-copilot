"""Measure matcher identity claims against declared gold pairs; never calibrate by fiat."""

import argparse
import json
from pathlib import Path


def evaluate_corpus(cases, maximum_false_unique=None):
    if maximum_false_unique is not None and (type(maximum_false_unique) is not int or maximum_false_unique < 0):
        raise ValueError("maximum_false_unique must be an explicitly chosen nonnegative integer")
    reports = []
    case_ids = set()
    for case in cases:
        identity = case["id"]
        if identity in case_ids:
            raise ValueError("duplicate corpus case ID")
        case_ids.add(identity)
        expected = dict(case["expectedPairs"])
        ambiguous = set(case.get("ambiguousReferenceIds", []))
        if (len(expected) != len(case["expectedPairs"]) or len(set(expected.values())) != len(expected)
                or expected.keys() & ambiguous):
            raise ValueError("gold pairs must be one-to-one and separate from ambiguous references")
        comparison = case["comparison"]
        if comparison.get("schema") == "workflow-result/v1":
            comparison = comparison["result"]
        mapping = [row for field in ("provisionalElements", "provisionalConnections") for row in comparison["mapping"][field]]
        selected = {(row["referenceId"], row["studentId"]) for row in mapping}
        if len(selected) != len(mapping) or len({r for r, s in selected}) != len(selected) or len({s for r, s in selected}) != len(selected):
            raise ValueError("comparison mapping must be one-to-one")
        unique = {}
        for fact in comparison["propertyFacts"]["items"]:
            if not fact["code"].startswith("identity.") or fact["evidence"].get("identityStatus") != "uniquely_supported":
                continue
            if len(fact["referenceIds"]) != 1 or len(fact["submissionIds"]) != 1:
                raise ValueError("unique identity must name one original pair")
            ref, sub = fact["referenceIds"][0], fact["submissionIds"][0]
            if ref in unique or (ref, sub) not in selected or ref not in expected.keys() | ambiguous:
                raise ValueError("identity claim is duplicated, unselected or absent from gold data")
            unique[ref] = sub
        wrong = [[ref, sub] for ref, sub in sorted(unique.items()) if expected.get(ref) != sub]
        correct = sum(expected.get(ref) == sub for ref, sub in unique.items())
        reports.append({"id": identity, "correctUnique": correct, "falseUnique": len(wrong),
                        "unresolvedExpected": len(expected.keys() - unique.keys()),
                        "ambiguousPreserved": len(ambiguous - unique.keys()), "wrongPairs": wrong,
                        "semanticConfiguration": comparison.get("semanticConfiguration", {})})
    totals = {key: sum(row[key] for row in reports) for key in
              ("correctUnique", "falseUnique", "unresolvedExpected", "ambiguousPreserved")}
    return {"schema": "identity-corpus-report/v1", "cases": reports, "totals": totals,
            "maximumFalseUnique": maximum_false_unique,
            "acceptance": "not_configured" if maximum_false_unique is None else
                          "within_declared_limit" if totals["falseUnique"] <= maximum_false_unique else "exceeds_declared_limit"}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("corpus", type=Path, help="JSON list with case ID, expectedPairs, ambiguousReferenceIds and comparison")
    cli.add_argument("--maximum-false-unique", type=int, help="Explicit project risk limit; absent means no acceptance decision")
    args = cli.parse_args()
    report = evaluate_corpus(json.loads(args.corpus.read_text(encoding="utf-8")), args.maximum_false_unique)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
