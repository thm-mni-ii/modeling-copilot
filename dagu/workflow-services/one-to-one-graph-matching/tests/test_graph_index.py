import unittest

from graph_index import GraphIndex


def node(identity, kind="modelElement", definition=None):
    return {
        "id": identity, "kind": kind, "type": kind, "comparisonGroup": None,
        "comparisonRole": "structural" if kind == "structuralElement" else "semantic",
        "language": {"languageId": "test", "versionId": "1"},
        "languageResolution": "resolved", "definition": definition,
    }


def graph(nodes, edges):
    return {"schemaVersion": 3, "languages": [], "nodes": nodes, "edges": edges}


class GraphIndexTests(unittest.TestCase):
    def test_containment_retains_intermediate_container_and_derived_owner(self):
        definition = {"languageId": "test", "versionId": "1", "path": "/elements/0/children/0"}
        index = GraphIndex(graph(
            [node("owner"), node("container", "structuralElement", definition), node("child")],
            [
                {"kind": "contains", "role": "component", "source": "container", "target": "owner"},
                {"kind": "contains", "role": "content", "source": "child", "target": "container"},
            ],
        ))
        self.assertEqual(index.parents["child"][0]["target"], "container")
        self.assertEqual(index.children["container"][0]["source"], "child")
        self.assertEqual(index.owner("child"), "owner")
        self.assertEqual(list(index.by_definition.values()), [["container"]])

    def test_endpoint_direction_and_open_endpoint_are_preserved(self):
        index = GraphIndex(graph(
            [node("a"), node("line", "connection")],
            [
                {"kind": "endpoint", "role": "source", "source": "a", "target": "line"},
                {"kind": "endpoint", "role": "target", "source": "line", "target": None},
            ],
        ))
        self.assertEqual(index.endpoints["line"], {"source": "a", "target": None})
        self.assertEqual(index.outgoing["a"][0]["kind"], "endpoint")
        self.assertEqual(index.parents["a"], [])

    def test_ambiguous_and_cyclic_owners_remain_unresolved(self):
        nodes = [node("a", "structuralElement"), node("b", "structuralElement"), node("c")]
        edges = [
            {"kind": "contains", "role": "component", "source": "a", "target": "b"},
            {"kind": "contains", "role": "component", "source": "b", "target": "a"},
            {"kind": "contains", "role": "content", "source": "c", "target": "a"},
            {"kind": "contains", "role": "content", "source": "c", "target": "b"},
        ]
        index = GraphIndex(graph(nodes, edges))
        self.assertIsNone(index.owner("a"))
        self.assertIsNone(index.owner("c"))

    def test_invalid_edges_and_duplicate_nodes_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            GraphIndex(graph([node("a"), node("a")], []))
        with self.assertRaisesRegex(ValueError, "unknown node"):
            GraphIndex(graph([node("a")], [
                {"kind": "contains", "role": "content", "source": "a", "target": "missing"},
            ]))
        with self.assertRaisesRegex(ValueError, "unique"):
            GraphIndex(graph([node("a"), node("b")], [
                {"id": "a", "kind": "contains", "role": "content", "source": "a", "target": "b"},
            ]))


if __name__ == "__main__":
    unittest.main()
