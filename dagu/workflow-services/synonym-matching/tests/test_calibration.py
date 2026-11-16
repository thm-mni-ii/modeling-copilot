import copy
import importlib.util
from pathlib import Path
import unittest

SERVICE_ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("calibrate_threshold", SERVICE_ROOT / "scripts/calibrate_threshold.py")
calibration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(calibration)


class LabelVariantCorpusTests(unittest.TestCase):
    def setUp(self):
        self.corpus = calibration.load_corpus()

    def test_every_typology_category_has_representative_cases(self):
        counts = calibration.validate_corpus(self.corpus)
        self.assertEqual(sorted(counts), sorted(f"{level}{number}" for level, size in
                                                (("A", 8), ("B", 2), ("C", 8), ("D", 6), ("E", 4), ("F", 2))
                                                for number in range(1, size + 1)))
        verdicts = {case["expected"] for case in self.corpus["cases"]}
        self.assertEqual(verdicts, set(calibration.EXPECTED))

    def test_invalid_corpus_entries_are_rejected(self):
        for change, message in ((lambda cases: cases.append(copy.deepcopy(cases[0])), "duplicate"),
                                (lambda cases: cases[0].update(id="Z9-01"), "category"),
                                (lambda cases: cases[0].update(expected="maybe"), "verdict"),
                                (lambda cases: cases[0].update(variant=" "), "labels")):
            corpus = copy.deepcopy(self.corpus)
            change(corpus["cases"])
            with self.subTest(message), self.assertRaisesRegex(ValueError, message):
                calibration.validate_corpus(corpus)

    def test_threshold_rule_mirrors_exact_anchor_and_is_monotonic(self):
        scored = calibration.score_cases(self.corpus["cases"])
        self.assertTrue(all(calibration.recognized(case, 1.0) for case in scored if case["exact"]))
        previous = None
        for threshold in calibration.THRESHOLDS:
            result = calibration.evaluate(scored, threshold)
            hits = result["tp"] + result["fp"]
            if previous is not None:
                self.assertLessEqual(hits, previous)
            previous = hits

    def test_casefold_only_raises_case_variant_scores(self):
        plain = {case["id"]: case["score"] for case in calibration.score_cases(self.corpus["cases"])}
        folded = {case["id"]: case["score"] for case in calibration.score_cases(self.corpus["cases"], "normalize+casefold")}
        self.assertEqual(folded["A1-02"], 1.0)
        self.assertLess(plain["A1-02"], 1.0)

    def test_report_covers_all_categories(self):
        report = calibration.render_report(self.corpus, (0.8,), detail=0.8)
        for category in self.corpus["categories"]:
            self.assertIn(f"| {category} |", report)


if __name__ == "__main__":
    unittest.main()
