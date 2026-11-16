"""Generic property regressions independent of semantic matching services."""

import unittest

from facts import evaluate_facts
from graph_index import GraphIndex
from initial_recognition import evaluate_connections
from test_graph_index import graph, node


def evaluate(reference, student=None, reference_edges=(), student_edges=None, pairs=None, complete=True, **extra):
    student = reference if student is None else student
    student_edges = reference_edges if student_edges is None else student_edges
    indices = {side: GraphIndex(graph(nodes, list(edges))) for side, nodes, edges in (
        ("reference", reference, reference_edges), ("student", student, student_edges))}
    if pairs is None:
        pairs = [(item["id"], item["id"]) for item in reference if item["kind"] in ("modelElement", "connection")]
    mapping = {"provisionalElements": [], "provisionalConnections": []}
    for ref, sub in pairs:
        field = "provisionalConnections" if indices["reference"].nodes[ref]["kind"] == "connection" else "provisionalElements"
        mapping[field].append({"referenceId": ref, "studentId": sub,
                               "reason": "unique_exact_label", "dependsOn": []})
    evaluation = {"mapping": mapping, **extra}
    evaluation["provisionalConnectionStructure"] = evaluate_connections(indices, mapping["provisionalElements"])
    graphs = {side: {"completeness": {"interpretation": "complete" if complete else "partial"}} for side in indices}
    return evaluate_facts(indices, evaluation, graphs, {"synonymMatrix": []})["items"]


def find(items, prefix, ref):
    return next(item for item in items if item["code"].startswith(prefix) and ref in item["referenceIds"])


class PropertyFactsTests(unittest.TestCase):
    def test_missing_and_unsupported_labels_are_not_evaluated(self):
        for reference_label, submission_label, statuses in (
            ("", "", {"reference": "missing", "student": "missing"}),
            ("Name", "", {"reference": "present", "student": "missing"}),
            (None, "Name", {"reference": "missing", "student": "present"}),
            ({"unexpected": "value"}, "Name", {"reference": "unsupported", "student": "present"}),
        ):
            with self.subTest(statuses=statuses):
                items = evaluate([{**node("r"), "label": reference_label}],
                                 [{**node("s"), "label": submission_label}], pairs=[("r", "s")])
                label = find(items, "label.", "r")
                self.assertEqual(label["status"], "not_evaluated")
                self.assertEqual(label["evidence"]["labelStatus"], statuses)
                self.assertEqual(label["code"], "label.unavailable")
                self.assertEqual(find(items, "type.", "r")["status"], "satisfied")

    def test_renamed_parent_keeps_child_supported_identity_and_label_difference(self):
        from correspondence_state import build_provisional_state
        from test_matching import make_inputs
        indices, candidates = make_inputs({"rp": "Old", "rc": "Unique"}, {"sp": "New", "sc": "Unique"},
                                          [("rp", "sp"), ("rc", "sc")], [contains("rc", "rp")], [contains("sc", "sp")])
        state = build_provisional_state(indices, candidates)
        parent = next(item for item in state["proposals"] if item["referenceId"] == "rp")
        self.assertEqual(parent["reason"], "independent_child_evidence")
        evaluation = {"mapping": {"provisionalElements": state["proposals"], "provisionalConnections": []}}
        graphs = {side: {"completeness": {"interpretation": "complete"}} for side in indices}
        items = evaluate_facts(indices, evaluation, graphs, candidates)["items"]
        self.assertEqual(find(items, "label.", "rp")["code"], "label.different")
        self.assertEqual(find(items, "children.", "rp")["status"], "satisfied")
        self.assertEqual(find(items, "owner.", "rc")["evidence"]["basis"], "conditional_mapping")

    def test_equal_label_survives_unresolved_type(self):
        left, right = node("r"), node("s")
        left["label"] = right["label"] = "Name"
        right["languageResolution"] = "unresolved"
        items = evaluate([left], [right], pairs=[("r", "s")])
        self.assertEqual(find(items, "label.", "r")["status"], "satisfied")
        self.assertEqual(find(items, "type.", "r")["status"], "not_evaluated")

    def test_unknown_containment_role_does_not_claim_owner_correctness(self):
        edges = [{"kind": "contains", "source": "child", "target": "parent", "role": None}]
        items = evaluate([node("parent"), node("child")], reference_edges=edges)
        self.assertEqual(find(items, "owner.", "child")["status"], "not_evaluated")
        self.assertEqual(find(items, "containment.", "child")["status"], "not_evaluated")

    def test_equal_concrete_type_and_different_label_do_not_reject_identity(self):
        left, right = {**node("r"), "label": "Old"}, {**node("s"), "label": "New"}
        items = evaluate([left], [right], pairs=[("r", "s")])
        self.assertEqual(find(items, "type.", "r")["status"], "satisfied")
        self.assertEqual(find(items, "label.", "r")["code"], "label.different")
        self.assertEqual(find(items, "label.", "r")["submissionIds"], ["s"])

    def test_complete_children_and_extra_child(self):
        nodes = [node("parent"), node("child")]
        edges = [contains("child", "parent")]
        self.assertEqual(find(evaluate(nodes, reference_edges=edges), "children.", "parent")["status"], "satisfied")
        items = evaluate(nodes, nodes + [node("extra")], edges, edges + [contains("extra", "parent")])
        self.assertEqual(find(items, "children.", "parent")["status"], "violated")

    def test_recognized_child_under_wrong_owner(self):
        nodes = [node("parent"), node("other"), node("child")]
        items = evaluate(nodes, reference_edges=[contains("child", "parent")], student_edges=[contains("child", "other")])
        self.assertEqual(find(items, "owner.", "child")["status"], "violated")
        self.assertEqual(find(items, "children.", "parent")["evidence"]["outsideReferenceIds"], ["child"])
        self.assertEqual(find(items, "type.", "child")["status"], "satisfied")

    def test_semantic_children_and_direct_containers_stay_separate(self):
        nodes = [node("parent"), node("box", "structuralElement"), node("child")]
        items = evaluate(nodes, reference_edges=[contains("box", "parent"), contains("child", "box")])
        self.assertEqual(find(items, "children.", "parent")["status"], "satisfied")
        self.assertEqual(find(items, "direct_children.", "parent")["status"], "unresolved")
        self.assertEqual(find(items, "owner.", "child")["status"], "satisfied")
        self.assertEqual(find(items, "containment.", "child")["status"], "unresolved")

    def test_separate_connection_endpoints_direction_and_type(self):
        from test_initial_connections import connection
        link, edges = connection("link", "a", "b")
        changed, wrong_edges = connection("link", "b", "a", connection_type="compatible")
        nodes = [node("a"), node("b"), link]
        items = evaluate(nodes, [node("a"), node("b"), changed], edges, wrong_edges)
        for prefix in ("connection.source", "connection.target", "connection.direction", "type."):
            self.assertEqual(find(items, prefix, "link")["status"], "violated")
        self.assertEqual(find(items, "connection.endpoints", "link")["status"], "satisfied")
        _, wrong_target = connection("link", "a", "c")
        items = evaluate(nodes + [node("c")], reference_edges=edges, student_edges=wrong_target)
        self.assertEqual(find(items, "connection.source", "link")["status"], "satisfied")
        self.assertEqual(find(items, "connection.target", "link")["status"], "violated")
        self.assertEqual(find(items, "connection.direction", "link")["status"], "unresolved")

    def test_global_connection_absence_is_direct_but_parent_absence_is_conditional(self):
        from test_initial_connections import connection
        link, edges = connection("link", "a", "b")
        items = evaluate([node("a"), node("b"), link], [node("a"), node("b")], edges, [], pairs=[("a", "a"), ("b", "b")])
        missing = find(items, "counterpart.", "link")
        self.assertEqual((missing["code"], missing["evidence"]["basis"]), ("counterpart.missing", "direct_observation"))
        local = find(items, "connections.outgoing_missing", "a")
        self.assertEqual(local["evidence"]["basis"], "conditional_mapping")
        partial = evaluate([node("a"), node("b"), link], [node("a"), node("b")], edges, [], pairs=[], complete=False)
        self.assertEqual(find(partial, "counterpart.", "link")["status"], "unresolved")

    def test_single_missing_child_requires_unique_remaining_class(self):
        nodes = [node("parent"), node("child")]
        items = evaluate(nodes, [node("parent")], [contains("child", "parent")], [], pairs=[("parent", "parent")])
        self.assertEqual(find(items, "counterpart.", "child")["code"], "counterpart.missing")
        self.assertEqual(find(items, "children.", "parent")["evidence"]["minimumMissing"], 1)
        items = evaluate(nodes + [node("other-child")], [node("parent")],
                         [contains("child", "parent"), contains("other-child", "parent")], [], pairs=[("parent", "parent")])
        self.assertFalse(any(item["code"] == "counterpart.missing" for item in items))
        self.assertEqual(find(items, "children.", "parent")["evidence"]["minimumMissing"], 2)

    def test_ambiguous_or_compatible_unassigned_child_never_claims_missing(self):
        nodes = [node("parent"), node("child")]
        for extra in ({}, {"decisionEvents": [{"referenceId": "child", "reasonCodes": ["ambiguous_candidates"]}]}):
            items = evaluate(nodes, nodes, [contains("child", "parent")], [], pairs=[("parent", "parent")], **extra)
            self.assertEqual(find(items, "counterpart.", "child")["status"], "unresolved")
        items = evaluate(nodes, [node("parent")], [contains("child", "parent")], [], pairs=[("parent", "parent")],
                         decisionEvents=[{"referenceId": "child", "reasonCodes": ["ambiguous_candidates"]}])
        self.assertEqual(find(items, "counterpart.", "child")["status"], "unresolved")

    def test_parallel_count_deficit_does_not_identify_missing_connection(self):
        from test_initial_connections import connection
        first, first_edges = connection("r1", "a", "b")
        second, second_edges = connection("r2", "a", "b")
        link, edges = connection("s1", "a", "b")
        items = evaluate([node("a"), node("b"), first, second], [node("a"), node("b"), link],
                         first_edges + second_edges, edges, pairs=[("a", "a"), ("b", "b")])
        self.assertFalse(any(item["code"] == "counterpart.missing" for item in items))
        self.assertEqual(find(items, "connection_group.minimum_missing", "r1")["evidence"]["minimumMissing"], 1)

    def test_open_connection_blocks_group_absence_and_complete_neighborhood(self):
        from test_initial_connections import connection
        link, edges = connection("r", "a", "b")
        open_link, open_edges = connection("s", "a", None)
        items = evaluate([node("a"), node("b"), link], [node("a"), node("b"), open_link],
                         edges, open_edges, pairs=[("a", "a"), ("b", "b")])
        self.assertEqual(find(items, "connection_group.minimum_missing", "r")["status"], "unresolved")
        self.assertEqual(find(items, "connections.complete", "a")["status"], "unresolved")


def contains(child, parent):
    return {"kind": "contains", "source": child, "target": parent, "role": "content"}


if __name__ == "__main__":
    unittest.main()
