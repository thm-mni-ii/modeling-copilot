import copy
import io
import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import main
from artifacts import GRAPH_HASH_FIELDS, content_hash
from test_artifacts import Store
from test_graph_index import node


def store_with_containment():
    store = Store()
    for side, key, child, parent in (
        ("reference", "ref", "r-child", "r1"),
        ("student", "submission", "s-child", "s1"),
    ):
        graph = store.files[f"graphs/{key}.json"]["result"]
        element = node(child)
        element["type"] = "attribute"
        graph["graph"]["nodes"].append(element)
        graph["graph"]["edges"].append({
            "kind": "contains", "role": "content", "source": child, "target": parent,
        })
        graph["graphHash"] = content_hash({field: graph[field] for field in GRAPH_HASH_FIELDS})
        inventory = store.files[f"labels/{key}.json"]["result"]
        inventory["graphHash"] = graph["graphHash"]
        inventory["elements"].append({
            "id": child, "type": "attribute", "comparisonGroup": None,
            "language": element["language"], "matchText": "Age",
            "labelStatus": "present", "textLanguage": "de",
        })
        inventory["inventoryHash"] = content_hash({
            field: value for field, value in inventory.items() if field != "inventoryHash"
        })
        store.candidates["graphHashes"][side] = graph["graphHash"]
        store.candidates["inventoryHashes"][side] = inventory["inventoryHash"]
    store.candidates["synonymMatrix"].append({
        "referenceElementId": "r-child", "referenceLabel": "Age",
        "matches": [{"submissionElementId": "s-child", "submissionLabel": "Age",
                     "comparisonBasis": "type", "scoreStatus": "scored", "scores": {"test": 1}}],
    })
    store.candidates["candidatePairCount"] = 2
    store.candidates["scoredPairCount"] = 2
    store.publish_candidates()
    return store


class MainTests(unittest.TestCase):
    def test_run_loads_valid_v1_artifacts_and_reports_provisional_coverage(self):
        store = Store()
        reference = store.files["graphs/ref.json"]["result"]
        extra = node("r2")
        extra["type"] = "other"
        reference["graph"]["nodes"].append(extra)
        student = store.files["graphs/submission.json"]["result"]
        student["graph"]["nodes"].extend([node("container", "structuralElement"), node("link", "connection")])
        for side, key, graph in (("reference", "ref", reference), ("student", "submission", student)):
            graph["graphHash"] = content_hash({field: graph[field] for field in GRAPH_HASH_FIELDS})
            inventory = store.files[f"labels/{key}.json"]["result"]
            inventory["graphHash"] = graph["graphHash"]
            if side == "reference":
                inventory["elements"].append({
                    "id": "r2", "type": "other", "comparisonGroup": None,
                    "language": extra["language"], "matchText": "Other",
                    "labelStatus": "present", "textLanguage": "de",
                })
            inventory["inventoryHash"] = content_hash({
                field: value for field, value in inventory.items() if field != "inventoryHash"
            })
            store.candidates["graphHashes"][side] = graph["graphHash"]
            store.candidates["inventoryHashes"][side] = inventory["inventoryHash"]
        store.candidates["synonymMatrix"].append({
            "referenceElementId": "r2", "referenceLabel": "Other", "matches": [],
        })
        store.publish_candidates()

        with patch.object(main, "read_artifacts", wraps=main.read_artifacts) as read:
            output = main.run(store, "ref")

        read.assert_called_once_with(store, "ref")
        self.assertEqual(output["schema"], "workflow-result/v1")
        self.assertEqual(output["mode"], "match")
        result = output["result"]
        self.assertEqual(result["schema"], "reference-comparison/v1")
        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["assessmentAvailable"])
        self.assertEqual(result["pair"], {"studentKey": "submission", "referenceKey": "ref"})
        self.assertEqual(result["metrics"]["overall"], {
            "referenceCount": 2, "studentCount": 1, "provisionalAnchorCount": 1,
            "maximumAssignableCount": 1, "anchorCoverage": 0.5, "capacityUpperBound": 0.5,
        })
        self.assertEqual(result["unresolvedReferenceIds"], ["r2"])
        self.assertEqual(result["mapping"]["provisionalElements"][0]["status"], "provisional")
        self.assertEqual(result["completeness"]["matching"], "provisional")
        self.assertEqual(result["completeness"]["structuralComparison"], "provisional_owner_and_connections")
        self.assertEqual(result["graphHashes"]["reference"], reference["graphHash"])
        self.assertEqual(result["candidateHash"], store.candidates["candidateHash"])
        self.assertEqual(result["comparisonHash"], content_hash({
            key: value for key, value in result.items() if key != "comparisonHash"
        }))
        self.assertEqual(main.run(store, "ref"), output)

    def test_run_reports_provisional_owner_consistency(self):
        result = main.run(store_with_containment(), "ref")["result"]
        self.assertEqual(result["metrics"]["provisionalOwnerConsistency"], {
            "expected": 1, "satisfied": 1, "violated": 0, "unresolved": 0,
            "agreement": {"lower": 1.0, "upper": 1.0},
        })
        self.assertEqual(result["metrics"]["overall"], {
            "referenceCount": 2, "studentCount": 2, "provisionalAnchorCount": 2,
            "maximumAssignableCount": 2, "anchorCoverage": 1.0, "capacityUpperBound": 1.0,
        })
        child = next(item for item in result["provisionalOwnerEvidence"] if item["referenceId"] == "r-child")
        self.assertEqual(child["status"], "satisfied")
        self.assertEqual(child["referenceContainmentPaths"], [["r-child", "r1"]])
        self.assertEqual(child["studentContainmentPaths"], [["s-child", "s1"]])
        owner_evidence = next(item for item in result["childOwnerEvidence"]
                              if item["referenceId"] == "r1" and item["studentId"] == "s1")
        self.assertEqual(owner_evidence["proposalStatus"], "reserved")
        self.assertEqual(owner_evidence["supportingChildren"][0]["referenceId"], "r-child")
        self.assertEqual(result["comparisonHash"], content_hash({
            key: value for key, value in result.items() if key != "comparisonHash"
        }))

    def test_connection_structure_is_included_in_feedback(self):
        store = Store()
        for side, key, element, connection_type in (
            ("reference", "ref", "r1", "first"),
            ("student", "submission", "s1", "second"),
        ):
            graph = store.files[f"graphs/{key}.json"]["result"]
            link = node(f"{element}-link", "connection")
            link.update({"type": connection_type, "comparisonGroup": "links", "directed": True})
            graph["graph"]["nodes"].append(link)
            graph["graph"]["edges"].extend([
                {"kind": "endpoint", "role": "source", "source": element, "target": link["id"]},
                {"kind": "endpoint", "role": "target", "source": link["id"], "target": element},
            ])
            graph["graphHash"] = content_hash({field: graph[field] for field in GRAPH_HASH_FIELDS})
            inventory = store.files[f"labels/{key}.json"]["result"]
            inventory["graphHash"] = graph["graphHash"]
            inventory["inventoryHash"] = content_hash({
                field: value for field, value in inventory.items() if field != "inventoryHash"
            })
            store.candidates["graphHashes"][side] = graph["graphHash"]
            store.candidates["inventoryHashes"][side] = inventory["inventoryHash"]
        store.publish_candidates()
        comparison = main.run(store, "ref")
        structure = comparison["result"]["provisionalConnectionStructure"]
        self.assertEqual(structure["completeness"], "complete")
        self.assertEqual(structure["byEndpoints"][0]["typeStatus"], "different")
        self.assertEqual(len(comparison["result"]["mapping"]["provisionalConnections"]), 1)
        type_comparison = comparison["result"]["provisionalTypeComparison"]
        self.assertEqual(type_comparison["connections"]["compatibleTypeDifferenceCount"], 1)
        self.assertEqual(type_comparison["connections"]["pairs"][0]["status"], "compatible_type_difference")
        store.files["comparisons/ref.json"] = comparison
        feedback_path = Path(__file__).resolve().parents[2] / "feedback-generation" / "src" / "main.py"
        spec = importlib.util.spec_from_file_location("feedback_generation", feedback_path)
        feedback = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(feedback)
        result = feedback.run(store, "ref")["result"]
        self.assertEqual(result["provisionalConnectionStructure"], structure)
        self.assertEqual(result["provisionalTypeComparison"], type_comparison)
        self.assertEqual(result["feedbackHash"], feedback.content_hash({
            key: value for key, value in result.items() if key != "feedbackHash"
        }))
        broken = copy.deepcopy(comparison)
        broken["result"]["provisionalTypeComparison"]["connections"]["pairs"][0]["status"] = "same_type"
        broken["result"]["comparisonHash"] = content_hash({
            key: value for key, value in broken["result"].items() if key != "comparisonHash"
        })
        store.files["comparisons/ref.json"] = broken
        with self.assertRaisesRegex(ValueError, "concrete type status"):
            feedback.run(store, "ref")
        broken = copy.deepcopy(comparison)
        broken["result"]["provisionalTypeComparison"]["connections"]["compatibleTypeDifferenceCount"] = 0
        broken["result"]["comparisonHash"] = content_hash({
            key: value for key, value in broken["result"].items() if key != "comparisonHash"
        })
        store.files["comparisons/ref.json"] = broken
        with self.assertRaisesRegex(ValueError, "type comparison counts"):
            feedback.run(store, "ref")
        legacy = copy.deepcopy(comparison)
        del legacy["result"]["provisionalTypeComparison"]
        legacy["result"]["comparisonHash"] = content_hash({
            key: value for key, value in legacy["result"].items() if key != "comparisonHash"
        })
        store.files["comparisons/ref.json"] = legacy
        self.assertNotIn("provisionalTypeComparison", feedback.run(store, "ref")["result"])

    def test_containment_relations_are_included_and_validated_in_feedback(self):
        store = store_with_containment()
        comparison = main.run(store, "ref")
        result = comparison["result"]
        metrics = result["metrics"]["provisionalContainment"]
        self.assertEqual(metrics, {
            "referenceRelationCount": 1, "satisfied": 1, "violated": 0, "unresolved": 0,
            "agreement": {"lower": 1.0, "upper": 1.0},
        })
        self.assertEqual(result["provisionalContainmentEvidence"][0]["decisionBasis"], "same_parent")
        store.files["comparisons/ref.json"] = comparison
        feedback_path = Path(__file__).resolve().parents[2] / "feedback-generation" / "src" / "main.py"
        spec = importlib.util.spec_from_file_location("feedback_generation", feedback_path)
        feedback = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(feedback)
        report = feedback.run(store, "ref")["result"]
        self.assertEqual(report["provisionalContainment"], {
            "metrics": metrics, "relations": result["provisionalContainmentEvidence"],
        })
        self.assertEqual(report["feedbackHash"], feedback.content_hash({
            key: value for key, value in report.items() if key != "feedbackHash"
        }))
        metrics["satisfied"] = 0
        result["comparisonHash"] = content_hash({key: value for key, value in result.items()
                                                  if key != "comparisonHash"})
        with self.assertRaisesRegex(ValueError, "containment counts"):
            feedback.run(store, "ref")

    def test_run_rejects_invalid_graph_and_candidate_hashes(self):
        for artifact in ("graph", "candidate"):
            with self.subTest(artifact=artifact):
                store = Store()
                if artifact == "graph":
                    store.files["graphs/ref.json"]["result"]["graph"]["nodes"][0]["type"] = "tampered"
                else:
                    store.candidates["synonymMatrix"][0]["referenceLabel"] = "tampered"
                with self.assertRaisesRegex(ValueError, f"{artifact} hash mismatch"):
                    main.run(store, "ref")

    def test_run_retains_partial_graph_interpretation(self):
        store = Store()
        reference = store.files["graphs/ref.json"]["result"]
        reference["completeness"]["interpretation"] = "partial"
        reference["graphHash"] = content_hash({field: reference[field] for field in GRAPH_HASH_FIELDS})
        inventory = store.files["labels/ref.json"]["result"]
        inventory["graphHash"] = reference["graphHash"]
        inventory["inventoryHash"] = content_hash({
            field: value for field, value in inventory.items() if field != "inventoryHash"
        })
        store.candidates["graphHashes"]["reference"] = reference["graphHash"]
        store.candidates["inventoryHashes"]["reference"] = inventory["inventoryHash"]
        store.publish_candidates()
        self.assertEqual(main.run(store, "ref")["result"]["completeness"]["interpretation"], "partial")

    def test_main_uses_workspace_and_reference_key(self):
        store = Store()
        with patch.dict(os.environ, {"WORKFLOW_EVALUATION_ID": "evaluation", "REFERENCE_KEY": "ref"}), \
                patch.object(main, "workspace", return_value=store), \
                patch.object(main, "write_output") as write:
            self.assertEqual(main.main(), 0)
        self.assertEqual(write.call_args.args[0]["result"]["evaluationId"], "evaluation")

    def test_main_reports_validation_error_without_publishing(self):
        store = Store()
        store.candidates["synonymMatrix"][0]["referenceLabel"] = "tampered"
        with patch.dict(os.environ, {"WORKFLOW_EVALUATION_ID": "evaluation", "REFERENCE_KEY": "ref"}), \
                patch.object(main, "workspace", return_value=store), \
                patch.object(main, "write_output") as write, \
                patch("sys.stderr", new_callable=io.StringIO) as stderr:
            self.assertEqual(main.main(), 1)
        write.assert_not_called()
        self.assertIn("candidate hash mismatch", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
