"""Graph context of elements: connections and placement, read without any language knowledge.

GM-47 (context disambiguates text): a text that reaches a tier for several candidates is resolved by the
candidate whose context agrees with already accepted pairs. GM-48 (neighbour structure): an element is
identified by at least two agreeing context relations without a text requirement (E1); a deviating label
stays a separate `label.*` fact. Both read only connections (type, direction) and containment, so a
container and a connection are simply two structures that are both searched.
"""

from collections import defaultdict

CONTEXT_REASON = "context_disambiguated_text"
NEIGHBOR_REASON = "neighbor_structure"


def _semantic_owner(index, identity):
    """The first model element above `identity`, climbing through structural containers."""
    current, seen = identity, {identity}
    while True:
        parents = [edge["target"] for edge in index.parents.get(current, ())]
        if len(parents) != 1 or parents[0] in seen or parents[0] not in index.nodes:
            return None
        parent = parents[0]
        seen.add(parent)
        kind = index.nodes[parent]["kind"]
        if kind == "modelElement":
            return parent
        if kind != "structuralElement":
            return None
        current = parent


def context_relations(index):
    """identity -> {(relation, connection type, direction, other element)}."""
    relations = defaultdict(set)
    for connection, ends in index.endpoints.items():
        node = index.nodes.get(connection) or {}
        source, target = ends.get("source"), ends.get("target")
        if node.get("kind") != "connection" or source is None or target is None:
            continue
        kind, directed = node.get("type"), node.get("directed") is True
        relations[source].add(("connection", kind, "out" if directed else "both", target))
        relations[target].add(("connection", kind, "in" if directed else "both", source))
    for identity, node in index.nodes.items():
        if node["kind"] != "modelElement":
            continue
        owner = _semantic_owner(index, identity)
        if owner is not None:
            relations[identity].add(("placed_in", None, None, owner))
            relations[owner].add(("holds", None, None, identity))
    return relations


class Context:
    """Agreement of candidate pairs with the accepted pairs, through the context of both elements."""

    def __init__(self, indices, proposals):
        self.relations = {side: context_relations(index) for side, index in indices.items()}
        self.mapping = {item["referenceId"]: item["studentId"] for item in proposals
                        if indices["reference"].nodes.get(item["referenceId"], {}).get("kind") == "modelElement"}
        self._cache = {}

    def support(self, pair):
        if pair not in self._cache:
            reference, student = pair
            observed = self.relations["student"].get(student, set())
            self._cache[pair] = {(other, self.mapping[other])
                                 for relation, kind, direction, other in self.relations["reference"].get(reference, ())
                                 if other in self.mapping and other != reference
                                 and (relation, kind, direction, self.mapping[other]) in observed}
        return self._cache[pair]


def _strict_best(pairs, context, minimum):
    """Pairs whose support reaches `minimum` and is strictly larger than that of every pair sharing an element."""
    by_reference, by_student = defaultdict(list), defaultdict(list)
    for pair in pairs:
        by_reference[pair[0]].append(pair)
        by_student[pair[1]].append(pair)
    chosen = []
    for pair in sorted(pairs):
        support = context.support(pair)
        rivals = [other for other in by_reference[pair[0]] + by_student[pair[1]] if other != pair]
        if len(support) >= minimum and all(len(context.support(other)) < len(support) for other in rivals):
            chosen.append(pair)
    return chosen


def _proposal(pair, context, reason):
    return {"referenceId": pair[0], "studentId": pair[1], "reason": reason,
            "dependsOn": [{"referenceId": r, "studentId": s} for r, s in sorted(context.support(pair))]}


def open_element_pairs(indices, state, reserved):
    used_ref, used_sub = reserved
    return {(item["referenceId"], item["studentId"]) for item in state["candidatePairs"]
            if item["referenceId"] not in used_ref and item["studentId"] not in used_sub
            and indices["reference"].nodes[item["referenceId"]]["kind"] == "modelElement"
            and indices["student"].nodes[item["studentId"]]["kind"] == "modelElement"}


def context_proposals(indices, state, reserved, text_ok):
    """GM-47: only among pairs the text admits, and only where the text alone leaves several candidates."""
    pairs = {pair for pair in open_element_pairs(indices, state, reserved) if text_ok(pair)}
    ambiguous = {pair for pair in pairs if any(other != pair and (other[0] == pair[0] or other[1] == pair[1]) for other in pairs)}
    context = Context(indices, state["proposals"])
    return [_proposal(pair, context, CONTEXT_REASON) for pair in _strict_best(ambiguous, context, 1)]


def neighbor_proposals(indices, state, reserved):
    """GM-48: at least two agreeing relations, strictly more than every rival of both elements."""
    pairs = open_element_pairs(indices, state, reserved)
    context = Context(indices, state["proposals"])
    return [_proposal(pair, context, NEIGHBOR_REASON) for pair in _strict_best(pairs, context, 2)]
