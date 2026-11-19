import copy
import unittest

from main import content_hash, run


SOURCE = {
    "key": "submission",
    "role": "submission",
    "label": "Submission",
    "modelId": "model-1",
    "versionId": "version-1",
}


def node(identity, kind, role, label, **fields):
    return {
        "id": identity,
        "kind": kind,
        "type": fields.pop("type", None),
        "comparisonGroup": fields.pop("comparisonGroup", None),
        "comparisonRole": role,
        "label": label,
        "language": fields.pop("language", None),
        "languageResolution": "resolved",
        "definition": None,
        **fields,
    }


def payload(nodes=None, edges=None):
    graph = {
        "schemaVersion": 1,
        "languages": [],
        "nodes": nodes if nodes is not None else [
            node("entity", "modelElement", "semantic", "<b>Stockwerk</b>", type="serm-entity",
                 comparisonGroup="serm-main", language={"languageId": "serm", "versionId": "1.0"},
                 properties={"textFormatting": {"fontStyle": 1, "bold": True, "italic": False, "underline": False}}),
            node("entity-copy", "modelElement", "semantic", "<b>Stockwerk</b>", type="serm-entity",
                 comparisonGroup="serm-main", language={"languageId": "serm", "versionId": "1.0"}),
            node("container", "structuralElement", "structural", "Attributes"),
            node("link", "connection", "unsupported", ""),
            node("cardinality", "connectionLabel", "unsupported", "1..n", connectionLabelId="cardinality"),
            node("role-label", "connectionLabel", "unsupported", "", connectionLabelId="role"),
            node("orphan-label", "connectionLabel", "unsupported", 42, connectionLabelId="role"),
            node("unknown", None, "unsupported", "Unknown"),
        ],
        "edges": edges if edges is not None else [
            {"kind": "contains", "role": "component", "source": "cardinality", "target": "link"},
            {"kind": "contains", "role": "component", "source": "role-label", "target": "link"},
        ],
    }
    data = {
        "schema": "graph-result/v1",
        "evaluationId": "evaluation-1",
        "source": copy.deepcopy(SOURCE),
        "inputHash": "1" * 64,
        "languageResources": [],
        "producer": {"service": "graph-parser", "version": "1.0.0", "resourceHash": "2" * 64},
        "graphHash": "",
        "graph": graph,
        "completeness": {"interpretation": "complete"},
        "diagnostics": [{"code": "PARSER_DIAGNOSTIC", "elementIds": ["entity"]}],
    }
    fields = ("source", "languageResources", "producer", "graph", "completeness", "diagnostics")
    data["graphHash"] = content_hash({field: data[field] for field in fields})
    return {
        "schema": "workflow-result/v1",
        "schemaVersion": 1,
        "status": "ok",
        "result": data,
    }


class ModelLabelExtractionTests(unittest.TestCase):
    def test_extracts_semantic_elements_and_separate_connection_texts(self):
        result = run(payload())["result"]

        self.assertEqual(result["schema"], "element-inventory/v1")
        self.assertEqual([item["id"] for item in result["elements"]], ["entity", "entity-copy"])
        self.assertEqual(result["elements"][0], {
            "id": "entity",
            "type": "serm-entity",
            "comparisonGroup": "serm-main",
            "language": {"languageId": "serm", "versionId": "1.0"},
            "matchText": "Stockwerk",
            "labelStatus": "present",
            "textLanguage": None,
        })
        self.assertNotIn("properties", result["elements"][0])
        self.assertEqual(result["connectionTexts"], [
            {"id": "orphan-label", "ownerConnectionId": None, "kind": "additionalLabel",
             "connectionLabelId": "role", "matchText": "", "labelStatus": "unsupported",
             "textLanguage": None},
            {"id": "cardinality", "ownerConnectionId": "link", "kind": "additionalLabel",
             "connectionLabelId": "cardinality", "matchText": "1..n", "labelStatus": "present",
             "textLanguage": None},
            {"id": "role-label", "ownerConnectionId": "link", "kind": "additionalLabel",
             "connectionLabelId": "role", "matchText": "", "labelStatus": "missing",
             "textLanguage": None},
            {"id": "link", "ownerConnectionId": "link", "kind": "self",
             "connectionLabelId": None, "matchText": "", "labelStatus": "missing",
             "textLanguage": None},
        ])
        self.assertIn("PARSER_DIAGNOSTIC", {item["code"] for item in result["diagnostics"]})
        self.assertIn("UNRESOLVED_CONNECTION_LABEL_OWNER", {item["code"] for item in result["diagnostics"]})
        self.assertIn("UNSUPPORTED_LABEL_TEXT", {item["code"] for item in result["diagnostics"]})
        self.assertEqual(result["completeness"]["interpretation"], "partial")

    def test_uml_text_labels_remain_independent_semantic_elements(self):
        request = payload(nodes=[
            node("class", "modelElement", "semantic", "Building", type="uml-class"),
            node("text", "modelElement", "semantic", "Room name", type="uml-text-label"),
            node("property-list", "structuralElement", "structural", "Attributes"),
        ], edges=[
            {"kind": "contains", "role": "content", "source": "text", "target": "class"},
        ])

        result = run(request)["result"]

        self.assertEqual([(item["id"], item["type"], item["matchText"]) for item in result["elements"]],
                         [("class", "uml-class", "Building"), ("text", "uml-text-label", "Room name")])

    def test_missing_label_is_retained_with_missing_status(self):
        request = payload(nodes=[
            node("entity", "modelElement", "semantic", "unused", type="serm-entity"),
        ], edges=[])
        del request["result"]["graph"]["nodes"][0]["label"]
        fields = ("source", "languageResources", "producer", "graph", "completeness", "diagnostics")
        request["result"]["graphHash"] = content_hash({
            field: request["result"][field] for field in fields
        })

        element = run(request)["result"]["elements"][0]

        self.assertEqual(element["matchText"], "")
        self.assertEqual(element["labelStatus"], "missing")

    def test_erm_connection_labels_are_bound_and_not_free_elements(self):
        request = payload(nodes=[
            node("entity", "modelElement", "semantic", "Entity", type="erm-entity"),
            node("attribute", "modelElement", "semantic", "Name", type="erm-attribute"),
            node("link", "connection", "unsupported", "Has"),
            node("cardinality", "connectionLabel", "unsupported", "1..n", connectionLabelId="cardinality"),
            node("role", "connectionLabel", "unsupported", "", connectionLabelId="role"),
        ], edges=[
            {"kind": "contains", "role": "component", "source": "cardinality", "target": "link"},
            {"kind": "contains", "role": "component", "source": "role", "target": "link"},
        ])

        result = run(request)["result"]

        self.assertEqual([item["id"] for item in result["elements"]], ["attribute", "entity"])
        self.assertEqual([(item["ownerConnectionId"], item["connectionLabelId"], item["labelStatus"])
                          for item in result["connectionTexts"]],
                         [("link", "cardinality", "present"), ("link", "role", "missing"),
                          ("link", None, "present")])

    def test_preserves_input_and_is_deterministic(self):
        request = payload()
        original = copy.deepcopy(request)

        first = run(request)
        second = run(request)

        self.assertEqual(request, original)
        self.assertEqual(first, second)
        self.assertEqual(first["result"]["inventoryHash"], content_hash({
            key: value for key, value in first["result"].items() if key != "inventoryHash"
        }))

    def test_owner_requires_one_connection_parent(self):
        request = payload(edges=[
            {"kind": "contains", "role": "component", "source": "cardinality", "target": "link"},
            {"kind": "contains", "role": "component", "source": "cardinality", "target": "other-link"},
        ])
        request["result"]["graph"]["nodes"].append(node("other-link", "connection", "unsupported", ""))
        fields = ("source", "languageResources", "producer", "graph", "completeness", "diagnostics")
        request["result"]["graphHash"] = content_hash({
            field: request["result"][field] for field in fields
        })

        result = run(request)["result"]
        cardinality = next(text for text in result["connectionTexts"] if text["id"] == "cardinality")

        self.assertIsNone(cardinality["ownerConnectionId"])
        self.assertIn("UNRESOLVED_CONNECTION_LABEL_OWNER", {item["code"] for item in result["diagnostics"]})

    def test_rejects_invalid_graph_hash(self):
        request = payload()
        request["result"]["graphHash"] = "0" * 64

        with self.assertRaisesRegex(ValueError, "graph hash"):
            run(request)

    def test_rejects_evaluation_mismatch_with_workspace(self):
        class Workspace:
            evaluation_id = "different-evaluation"

            def snapshot(self):
                return {"inputHash": "1" * 64, "models": []}

        with self.assertRaisesRegex(ValueError, "frozen evaluation input"):
            run(payload(), Workspace())


if __name__ == "__main__":
    unittest.main()
