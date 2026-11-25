"""Graph context of elements: connections and placement, read without any language knowledge.

GM-47 (context disambiguates text): a text that reaches a tier for several candidates is resolved by the
candidate whose context agrees with already accepted pairs. GM-48 (neighbour structure): an element is
identified by at least two agreeing context relations without a text requirement (E1); a deviating label
stays a separate `label.*` fact. Both read only connections (type, direction) and containment, so a
container and a connection are simply two structures that are both searched.

GM-51 (duplicates), only after both found nothing: an edge to the right neighbour still counts when its
type or direction deviates, which keeps the deviation a `connection.*` fact instead of hiding the element;
text candidates that nothing distinguishes at all are equally right and are paired in ID order (as GM-46).
"""

from collections import defaultdict

CONTEXT_REASON = "context_disambiguated_text"
NEIGHBOR_REASON = "neighbor_structure"
LOOSE_CONTEXT_REASON = "loose_context_text"
INTERCHANGEABLE_REASON = "interchangeable_duplicate"


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

    def __init__(self, indices, proposals, loose=False):
        self.relations = {side: context_relations(index) for side, index in indices.items()}
        # Loose: an edge between the right elements counts whatever its type and direction.
        self.loose = loose
        self.mapping = {item["referenceId"]: item["studentId"] for item in proposals
                        if indices["reference"].nodes.get(item["referenceId"], {}).get("kind") == "modelElement"}
        self._cache = {}

    def support(self, pair):
        if pair not in self._cache:
            reference, student = pair
            def key(relation, kind, direction, other):
                return (relation, other) if self.loose else (relation, kind, direction, other)
            observed = {key(*item) for item in self.relations["student"].get(student, set())}
            self._cache[pair] = {(other, self.mapping[other])
                                 for relation, kind, direction, other in self.relations["reference"].get(reference, ())
                                 if other in self.mapping and other != reference
                                 and key(relation, kind, direction, self.mapping[other]) in observed}
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


def _ambiguous_text_pairs(indices, state, reserved, text_ok):
    pairs = {pair for pair in open_element_pairs(indices, state, reserved) if text_ok(pair)}
    return {pair for pair in pairs if any(other != pair and (other[0] == pair[0] or other[1] == pair[1]) for other in pairs)}


def context_proposals(indices, state, reserved, text_ok, loose=False):
    """GM-47 (GM-51 when loose): only among pairs the text admits, and only where the text alone leaves several candidates."""
    context = Context(indices, state["proposals"], loose)
    return [_proposal(pair, context, LOOSE_CONTEXT_REASON if loose else CONTEXT_REASON)
            for pair in _strict_best(_ambiguous_text_pairs(indices, state, reserved, text_ok), context, 1)]


def interchangeable_proposals(indices, state, reserved, text_ok):
    """GM-51: a group of text candidates whose elements no context tells apart; any one-to-one pairing is equally right."""
    pairs = _ambiguous_text_pairs(indices, state, reserved, text_ok)
    mapping = {item["referenceId"]: item["studentId"] for item in state["proposals"]}
    known = {"reference": {identity: identity for identity in mapping}, "student": {s: r for r, s in mapping.items()}}
    relations = {side: context_relations(index) for side, index in indices.items()}

    def signature(side, identity):
        """Context in reference terms: identified neighbours by identity, open ones by type and text."""
        nodes = indices[side].nodes
        return sorted(repr((relation, kind, direction, known[side].get(other)
                            or (nodes[other]["type"], " ".join(str(nodes[other].get("label") or "").casefold().split()))))
                      for relation, kind, direction, other in relations[side].get(identity, ()))

    groups, seen = [], set()
    for start in sorted(pairs):
        if start in seen:
            continue
        group, todo = set(), [start]
        while todo:
            pair = todo.pop()
            if pair in group:
                continue
            group.add(pair)
            todo += [other for other in pairs if other[0] == pair[0] or other[1] == pair[1]]
        seen |= group
        groups.append(group)
    proposals = []
    for group in groups:
        references, students = sorted({r for r, _ in group}), sorted({s for _, s in group})
        if (len(group) == len(references) * len(students)
                and len({repr(signature("reference", r)) for r in references}) == 1
                and len({repr(signature("student", s)) for s in students}) == 1):
            proposals += [{"referenceId": r, "studentId": s, "reason": INTERCHANGEABLE_REASON, "dependsOn": []}
                          for r, s in zip(references, students)]
    return proposals


def neighbor_proposals(indices, state, reserved):
    """GM-48: at least two agreeing relations, strictly more than every rival of both elements."""
    pairs = open_element_pairs(indices, state, reserved)
    context = Context(indices, state["proposals"])
    return [_proposal(pair, context, NEIGHBOR_REASON) for pair in _strict_best(pairs, context, 2)]
