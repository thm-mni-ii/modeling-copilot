"""Gold data must detect wrong certainty and never silently choose a risk limit."""

import importlib.util
from pathlib import Path
import unittest

from correspondence_state import build_provisional_state
from facts import evaluate_facts
from identity_evidence import evaluate_identity
from test_matching import make_inputs

spec = importlib.util.spec_from_file_location("evaluate_corpus", Path(__file__).resolve().parents[1] / "scripts/evaluate_corpus.py")
corpus = importlib.util.module_from_spec(spec)
spec.loader.exec_module(corpus)


def exact_case():
    indices, candidates = make_inputs({"r": "Alpha"}, {"s": "Alpha"}, [("r", "s")])
    state = build_provisional_state(indices, candidates)
    comparison = {"mapping": {"provisionalElements": state["proposals"], "provisionalConnections": []},
                  "identityEvidence": evaluate_identity(indices, candidates, state["proposals"])}
    comparison["propertyFacts"] = evaluate_facts(indices, comparison,
        {side: {"completeness": {"interpretation": "complete"}} for side in indices}, candidates)
    return {"id": "exact", "expectedPairs": [["r", "s"]], "comparison": comparison}


class CorpusTests(unittest.TestCase):
    def test_actual_matcher_claim_and_wrong_gold_are_distinguished(self):
        case = exact_case()
        result = corpus.evaluate_corpus([case])
        self.assertEqual(result["totals"]["correctUnique"], 1)
        self.assertEqual(result["acceptance"], "not_configured")
        case["expectedPairs"] = [["r", "other"]]
        result = corpus.evaluate_corpus([case], maximum_false_unique=0)
        self.assertEqual(result["totals"]["falseUnique"], 1)
        self.assertEqual(result["acceptance"], "exceeds_declared_limit")

    def test_ambiguity_and_unconfirmed_expected_pairs_remain_visible(self):
        case = exact_case()
        case["comparison"]["propertyFacts"]["items"] = []
        result = corpus.evaluate_corpus([case])
        self.assertEqual(result["totals"]["unresolvedExpected"], 1)
        case.update(expectedPairs=[], ambiguousReferenceIds=["r"])
        self.assertEqual(corpus.evaluate_corpus([case])["totals"]["ambiguousPreserved"], 1)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            corpus.evaluate_corpus([case, case])


if __name__ == "__main__":
    unittest.main()
