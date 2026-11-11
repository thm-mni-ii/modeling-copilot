import unittest

from parser import parse_model


SOURCE = {
    "key": "submission",
    "role": "submission",
    "label": "Submission",
    "modelId": "model-1",
    "versionId": "version-1",
}


def parse(cells, elements, connections=None, language_id="test", groups=None):
    language_data = {
        "elements": elements,
        "connections": connections or [],
        "evaluation": {"comparisonGroups": groups or []},
    }
    xml = (
        '<GraphDataModel><root><Cell id="canvas"/>'
        '<Cell id="modeling" parent="canvas"/>'
        '<Cell id="feedback" parent="canvas"/>'
        f'{"".join(cells)}</root></GraphDataModel>'
    )
    return parse_model({
        "source": SOURCE,
        "model": {"format": "maxgraph-xml", "version": 1, "xml": xml},
        "languages": [{"languageId": language_id, "versionId": "1.0", "data": language_data}],
    })


def node_by_id(result, identity):
    return next(node for node in result["graph"]["nodes"] if node["id"] == identity)


class GraphParserTests(unittest.TestCase):
    def test_graph_v3_omits_redundant_fields_and_empty_optional_fields(self):
        result = parse(
            [
                '<Cell id="item" value="Item" diagramElementType="item" vertex="1" parent="modeling"/>',
                '<Cell id="custom" diagramElementType="custom" vertex="1" parent="modeling">'
                '<Object marker="preserved" as="diagramAttributes"/></Cell>',
            ],
            [{"type": "item"}, {"type": "custom"}],
        )

        graph = result["graph"]
        node = node_by_id(result, "item")
        custom = node_by_id(result, "custom")
        self.assertEqual(graph["schemaVersion"], 3)
        self.assertNotIn("excluded", graph)
        self.assertNotIn("category", node)
        self.assertFalse({"nativeType", "origin", "properties", "definitionCandidates"} & node.keys())
        self.assertEqual(custom["properties"], {"marker": "preserved"})
        self.assertEqual(graph["edges"], [])

    def test_serm_containment_keeps_structural_container_and_attribute_instance(self):
        result = parse(
            [
                '<Cell id="entity" value="Entity" diagramElementType="serm-entity" vertex="1" parent="modeling"/>',
                '<Cell id="attributes" value="" diagramElementType="serm-attribute-list" vertex="1" parent="entity"/>',
                '<Cell id="attribute" value="Name" diagramElementType="serm-attribute" vertex="1" parent="attributes"/>',
            ],
            [
                {"id": "entity", "type": "serm-entity", "children": [
                    {"id": "attribute-list", "type": "serm-attribute-list"},
                ]},
                {"id": "attribute-list", "type": "serm-attribute-list"},
                {"id": "attribute", "type": "serm-attribute"},
            ],
            language_id="serm",
            groups=[{"id": "serm-attribute", "name": "Attribute",
                     "elementTypes": ["serm-attribute", "serm-key-attribute"]}],
        )

        container = node_by_id(result, "attributes")
        attribute = node_by_id(result, "attribute")
        self.assertEqual(container["kind"], "structuralElement")
        self.assertEqual(container["definition"]["path"], "/elements/0/children/0")
        self.assertEqual(container["label"], "")
        self.assertEqual(attribute["kind"], "modelElement")
        self.assertEqual(attribute["comparisonGroup"], "serm-attribute")
        contains = {(edge["source"], edge["target"]) for edge in result["graph"]["edges"]
                    if edge["kind"] == "contains"}
        self.assertEqual(contains, {("attributes", "entity"), ("attribute", "attributes")})
        self.assertEqual({edge["role"] for edge in result["graph"]["edges"]}, {"component", "content"})

    def test_multiple_declared_containers_keep_distinct_definition_references(self):
        result = parse(
            [
                '<Cell id="parent" diagramElementType="parent" vertex="1" parent="modeling"/>',
                '<Cell id="left" diagramElementType="left-container" vertex="1" parent="parent"/>',
                '<Cell id="right" diagramElementType="right-container" vertex="1" parent="parent"/>',
                '<Cell id="left-item" diagramElementType="left-item" vertex="1" parent="left"/>',
                '<Cell id="right-item" diagramElementType="right-item" vertex="1" parent="right"/>',
            ],
            [{"type": "parent", "children": [
                {"id": "left", "type": "left-container", "children": [{"type": "left-item"}]},
                {"id": "right", "type": "right-container", "children": [{"type": "right-item"}]},
            ]}],
        )

        left = node_by_id(result, "left")
        right = node_by_id(result, "right")
        self.assertEqual(left["kind"], "structuralElement")
        self.assertEqual(right["kind"], "structuralElement")
        self.assertEqual(left["definition"]["definitionId"], "left")
        self.assertEqual(right["definition"]["definitionId"], "right")
        self.assertNotEqual(left["definition"]["path"], right["definition"]["path"])
        self.assertEqual(node_by_id(result, "left-item")["kind"], "structuralElement")
        self.assertEqual(node_by_id(result, "right-item")["kind"], "structuralElement")

    def test_uml_text_label_is_an_independent_model_element(self):
        result = parse(
            [
                '<Cell id="class" diagramElementType="uml-class" vertex="1" parent="modeling"/>',
                '<Cell id="text" value="Class note" diagramElementType="uml-text-label" vertex="1" parent="class"/>',
            ],
            [{"type": "uml-class"}, {"type": "uml-text-label"}],
            language_id="uml",
        )

        label = node_by_id(result, "text")
        self.assertEqual(label["kind"], "modelElement")
        self.assertEqual(label["label"], "Class note")
        self.assertIsNone(label["comparisonGroup"])
        self.assertEqual(
            [(edge["source"], edge["target"]) for edge in result["graph"]["edges"] if edge["kind"] == "contains"],
            [("text", "class")],
        )

    def test_erm_connection_and_labels_remain_separate_from_containment(self):
        result = parse(
            [
                '<Cell id="entity" diagramElementType="erm-entity" vertex="1" parent="modeling"/>',
                '<Cell id="attribute" diagramElementType="erm-attribute" vertex="1" parent="modeling"/>',
                '<Cell id="link" connectionId="erm-attribute-link" edge="1" parent="modeling" source="entity" target="attribute"/>',
                '<Cell id="cardinality" connectionLabelId="cardinality" value="1..n" parent="link"/>',
                '<Cell id="role" connectionLabelId="role" value="owner" parent="link"/>',
            ],
            [{"type": "erm-entity"}, {"type": "erm-attribute"}],
            [{"type": "erm-attribute-link", "additionalLabels": [
                {"type": "cardinality"}, {"type": "role"},
            ]}],
            language_id="erm",
        )

        connection = node_by_id(result, "link")
        self.assertEqual(connection["kind"], "connection")
        self.assertEqual(connection["type"], "erm-attribute-link")
        self.assertIs(connection["directed"], True)
        self.assertEqual(node_by_id(result, "cardinality")["kind"], "connectionLabel")
        self.assertEqual(node_by_id(result, "role")["connectionLabelId"], "role")
        contains = {(edge["source"], edge["target"], edge["role"]) for edge in result["graph"]["edges"]
                    if edge["kind"] == "contains"}
        self.assertEqual(contains, {("cardinality", "link", "component"), ("role", "link", "component")})
        endpoints = {edge["role"]: (edge["source"], edge["target"]) for edge in result["graph"]["edges"]
                     if edge["kind"] == "endpoint"}
        self.assertEqual(endpoints, {"source": ("entity", "link"), "target": ("link", "attribute")})
        self.assertTrue(all(set(edge) <= {"id", "kind", "role", "source", "target"}
                            for edge in result["graph"]["edges"]))

    def test_unknown_types_missing_references_and_ambiguous_children_are_diagnosed(self):
        result = parse(
            [
                '<Cell id="unknown" diagramElementType="unlisted-type" vertex="1" parent="modeling"/>',
                '<Cell id="orphan" value="Orphan" diagramElementType="unlisted-orphan" vertex="1" parent="missing-parent"/>',
                '<Cell id="link" connectionId="known-link" edge="1" parent="modeling" source="missing-endpoint" target="unknown"/>',
            ],
            [{"type": "parent", "children": [{"type": "slot"}, {"type": "slot"}]},
             {"type": "parent"}],
            [{"type": "known-link"}],
        )
        unknown = node_by_id(result, "unknown")
        self.assertEqual(unknown["type"], "unlisted-type")
        self.assertEqual(unknown["kind"], "modelElement")
        self.assertNotIn("definitionCandidates", unknown)
        invalid_owner = next(item for item in result["diagnostics"] if item["code"] == "INVALID_OWNER")
        self.assertEqual(invalid_owner["elementIds"], ["orphan"])
        self.assertEqual(invalid_owner["label"], "Orphan")
        codes = {diagnostic["code"] for diagnostic in result["diagnostics"]}
        self.assertTrue({"UNRESOLVED_DEFINITION", "INVALID_OWNER", "OPEN_ENDPOINT"} <= codes)

        ambiguous = parse(
            [
                '<Cell id="parent" diagramElementType="parent" vertex="1" parent="modeling"/>',
                '<Cell id="slot" diagramElementType="slot" vertex="1" parent="parent"/>',
            ],
            [{"type": "parent", "children": [{"type": "slot"}, {"type": "slot"}]}],
        )
        ambiguous_slot = node_by_id(ambiguous, "slot")
        self.assertIsNone(ambiguous_slot["kind"])
        self.assertEqual(len(ambiguous_slot["definitionCandidates"]), 2)
        self.assertIn("UNRESOLVED_CHILD_DEFINITION", {item["code"] for item in ambiguous["diagnostics"]})


if __name__ == "__main__":
    unittest.main()
