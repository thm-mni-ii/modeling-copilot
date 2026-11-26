"""Rank already computed text evidence of open elements into synonym suggestions.

Runs after graph matching on frozen workspace artifacts. It computes no new similarity and decides
nothing: a signal is only ever a suggestion for an administrator. Works from the graph contract alone.
"""

from collections import defaultdict
import os
import re

from workflow_io import identifier
from .provenance import SERVICE, producer_metadata
from .term_key import TERM_NORMALIZATION, term_key

BASIS_ORDER = ("owner", "endpoints", "neighbors")
EVIDENCE_ORDER = {"context_unique": 0, "context_best": 1, "text_only": 2}
MAX_TERM_LENGTH = 256  # the glossary cannot store longer terms


def signal_request():
    """Signal mode is selected by the input path, because the service server allows no new variable."""
    relative = os.environ.get("WORKFLOW_INPUT_PATH", "")
    if not relative.startswith("comparisons/"):
        return None
    reference_key = identifier(os.environ.get("REFERENCE_KEY"))
    if relative != f"comparisons/{reference_key}.json" or os.environ.get("WORKFLOW_OUTPUT_PATH") != f"signals/{reference_key}.json":
        raise ValueError("signal mode needs comparisons/<REFERENCE_KEY>.json and signals/<REFERENCE_KEY>.json")
    return reference_key


def _result(envelope, capability, schema):
    if (not isinstance(envelope, dict) or envelope.get("status") != "ok" or envelope.get("capability") != capability
            or not isinstance(envelope.get("result"), dict) or envelope["result"].get("schema") != schema):
        raise ValueError(f"expected successful {capability} {schema} artifact")
    return envelope["result"]


class _Graph:
    """Owners, endpoints and connection neighbours of one parsed model."""

    def __init__(self, graph):
        self.nodes = {node["id"]: node for node in graph["nodes"]}
        self.parents, self.endpoints = defaultdict(list), defaultdict(dict)
        for edge in graph["edges"]:
            if edge["kind"] == "contains":
                self.parents[edge["source"]].append(edge)
            elif edge["role"] == "source" and edge["source"] is not None:
                self.endpoints[edge["target"]]["source"] = edge["source"]
            elif edge["role"] == "target" and edge["target"] is not None:
                self.endpoints[edge["source"]]["target"] = edge["target"]
        self.neighbors = defaultdict(set)
        for connection, ends in self.endpoints.items():
            if len(ends) == 2:
                self.neighbors[ends["source"]].add(ends["target"])
                self.neighbors[ends["target"]].add(ends["source"])

    def owner(self, identity):
        """Nearest non-structural parent reached through a declared component relation."""
        visited, current, declared = {identity}, identity, False
        while True:
            edges = self.parents.get(current, ())
            if len(edges) != 1:
                return None
            declared = declared or edges[0]["role"] == "component"
            current = edges[0]["target"]
            if current in visited:
                return None
            visited.add(current)
            if self.nodes[current]["kind"] != "structuralElement":
                return current if declared else None


def _comparison_key(node):
    language = node.get("language")
    if not language:
        return None
    group, node_type = node.get("comparisonGroup"), node.get("type")
    if group is None and not node_type:
        return None
    basis, value = ("group", group) if group is not None else ("type", node_type)
    return f'{node["kind"]}|{language["languageId"]}|{language["versionId"]}|{basis}|{value}'


def _recognized(comparison):
    """The same definition the feedback counts as recognized: uniquely supported identity facts."""
    pairs = {}
    for fact in comparison["propertyFacts"]["items"]:
        if (fact["code"].startswith("identity.") and fact["evidence"].get("identityStatus") == "uniquely_supported"
                and len(fact["referenceIds"]) == len(fact["submissionIds"]) == 1):
            pairs[fact["referenceIds"][0]] = fact["submissionIds"][0]
    return pairs


def _digit_conflict(left, right):
    left_digits, right_digits = re.findall(r"\d+", left), re.findall(r"\d+", right)
    return bool(left_digits and right_digits and left_digits != right_digits)


def _floors(graph_matching):
    """Lowest frozen acceptance level per method across all tiers and confirmation floors."""
    floors = {}
    for tier in graph_matching.get("textEvidence", {}).get("tiers", []):
        for values in (tier["minimumSimilarity"], tier.get("confirmationFloor", {})):
            for method, value in values.items():
                floors[method] = min(value, floors.get(method, value))
    return floors


def _rank(scores):
    return max(scores.values(), default=0.0)


def _unique_best(pairs, side):
    """For each element on one side, its strictly best partner; ties have none."""
    grouped = defaultdict(list)
    for pair in pairs:
        grouped[pair["ref" if side == "ref" else "sub"]].append(pair)
    best = {}
    for identity, rows in grouped.items():
        top = max(_rank(row["scores"]) for row in rows)
        leaders = [row for row in rows if _rank(row["scores"]) == top]
        if len(leaders) == 1:
            best[identity] = leaders[0]
    return best


def _mutual_best(pairs):
    by_reference, by_submission = _unique_best(pairs, "ref"), _unique_best(pairs, "sub")
    return {(row["ref"], row["sub"]) for row in by_reference.values() if by_submission.get(row["sub"]) is row}


def _candidates(candidates, graphs, recognized):
    """Open pairs of the frozen matrices; both sides have the same language and comparison group."""
    reference, student = graphs["reference"], graphs["student"]
    mapped_subs = set(recognized.values())
    pairs = []

    def add(ref, sub, ref_label, sub_label, scores, kind):
        left, right = reference.nodes.get(ref), student.nodes.get(sub)
        if (ref in recognized or sub in mapped_subs or left is None or right is None or not isinstance(scores, dict) or not scores
                or left["kind"] != right["kind"] or left.get("comparisonRole") != "semantic" or right.get("comparisonRole") != "semantic"):
            return
        key, other = _comparison_key(left), _comparison_key(right)
        term = term_key(sub_label)
        if (key is None or key != other or not term or len(sub_label) > MAX_TERM_LENGTH or len(term) > MAX_TERM_LENGTH
                or term == term_key(ref_label) or _digit_conflict(ref_label, sub_label)):
            return
        ref_owner, sub_owner = reference.owner(ref), student.owner(sub)
        if ref_owner is not None and sub_owner is not None and recognized.get(ref_owner) != sub_owner and (
                ref_owner in recognized or sub_owner in mapped_subs):
            return
        pairs.append({"ref": ref, "sub": sub, "text": sub_label, "termKey": term, "key": key, "kind": kind,
                      "scores": dict(sorted(scores.items()))})

    for row in candidates["synonymMatrix"]:
        for match in row["matches"]:
            if match["scoreStatus"] == "scored":
                add(row["referenceElementId"], match["submissionElementId"], row["referenceLabel"],
                    match["submissionLabel"], match["scores"], "element")
    for row in candidates["connectionTextMatrix"]:
        if row["kind"] == "self":
            add(row["referenceOwnerConnectionId"], row["submissionOwnerConnectionId"], row["referenceLabel"],
                row["submissionLabel"], row["scores"], "connection")
    return pairs


def _open_items(inventory, graph, excluded):
    """Open semantic elements and connections with own text, by comparison key."""
    items = {}
    for element in inventory["elements"]:
        if element["labelStatus"] == "present" and element["id"] not in excluded:
            items[element["id"]] = element["matchText"]
    for text in inventory["connectionTexts"]:
        node = graph.nodes.get(text["id"])
        if (text["kind"] == "self" and text["labelStatus"] == "present" and text["id"] not in excluded
                and node is not None and node.get("comparisonRole") == "semantic"):
            items[text["id"]] = text["matchText"]
    return items


def _contexts(graphs, recognized, open_refs, open_subs):
    """Context id -> open reference and submission members, per basis and comparison key."""
    reference, student = graphs["reference"], graphs["student"]
    inverse = {sub: ref for ref, sub in recognized.items()}
    contexts = {basis: defaultdict(lambda: {"refs": set(), "subs": set()}) for basis in BASIS_ORDER}

    def members(graph, identity, mapped, side):
        node = graph.nodes[identity]
        key = _comparison_key(node)
        if key is None:
            return
        owner = graph.owner(identity)
        if owner in mapped:
            anchor = owner if side == "refs" else mapped[owner]
            contexts["owner"][(anchor, key)][side].add(identity)
        ends = graph.endpoints.get(identity, {})
        if node["kind"] == "connection":
            source, target = ends.get("source"), ends.get("target")
            if source in mapped and target in mapped:
                first, second = (source, target) if side == "refs" else (mapped[source], mapped[target])
                anchor = (first, second) if node.get("directed") is True else tuple(sorted((first, second)))
                contexts["endpoints"][(anchor, node.get("directed") is True, key)][side].add(identity)
            touching = {end for end in (source, target) if end in mapped}
        else:
            touching = {other for other in graph.neighbors.get(identity, ()) if other in mapped}
        for other in touching:
            anchor = other if side == "refs" else mapped[other]
            contexts["neighbors"][(anchor, key)][side].add(identity)

    for identity in open_refs:
        members(reference, identity, recognized, "refs")
    for identity in open_subs:
        members(student, identity, inverse, "subs")
    return contexts


def build_signals(candidates, comparison, graphs, inventories, graph_matching):
    recognized = _recognized(comparison)
    open_refs = _open_items(inventories["reference"], graphs["reference"], set(recognized))
    open_subs = _open_items(inventories["student"], graphs["student"], set(recognized.values()))
    pairs = [pair for pair in _candidates(candidates, graphs, recognized)
             if pair["ref"] in open_refs and pair["sub"] in open_subs]
    contexts = _contexts(graphs, recognized, open_refs, open_subs)
    floors = _floors(graph_matching)
    by_id = {(pair["ref"], pair["sub"]): pair for pair in pairs}
    verdicts = {}

    def record(pair, evidence, basis):
        current = verdicts.get((pair["ref"], pair["termKey"]))
        rank = (EVIDENCE_ORDER[evidence], BASIS_ORDER.index(basis) if basis in BASIS_ORDER else 3, pair["text"], pair["sub"])
        if current is None or rank < current[0]:
            verdicts[(pair["ref"], pair["termKey"])] = (rank, pair, evidence, basis)

    assigned = set()
    for basis in BASIS_ORDER:
        scoped = defaultdict(list)
        for context, members in contexts[basis].items():
            for ref in members["refs"]:
                for sub in members["subs"]:
                    if (ref, sub) in by_id and (ref, sub) not in assigned:
                        scoped[context].append(by_id[(ref, sub)])
        for context, rows in scoped.items():
            members = contexts[basis][context]
            texts = {term_key(open_subs[sub]) for sub in members["subs"]}
            best = _mutual_best(rows)
            for row in rows:
                if len(members["refs"]) == 1 and len(texts) == 1:
                    record(row, "context_unique", basis)
                elif (row["ref"], row["sub"]) in best:
                    record(row, "context_best", basis)
        assigned |= {(row["ref"], row["sub"]) for rows in scoped.values() for row in rows}
    for key in sorted({pair["key"] for pair in pairs}):
        rows = [pair for pair in pairs if pair["key"] == key]
        best = _mutual_best(rows)
        for row in rows:
            if (row["ref"], row["sub"]) in assigned or (row["ref"], row["sub"]) not in best:
                continue
            if any(method in floors and score >= floors[method] for method, score in row["scores"].items()):
                record(row, "text_only", "none")
    signals = [{"referenceElementId": pair["ref"], "targetKind": pair["kind"], "comparisonKey": pair["key"],
                "term": pair["text"], "termKey": pair["termKey"], "evidence": evidence, "contextBasis": basis,
                "scores": pair["scores"]}
               for _rank_key, pair, evidence, basis in verdicts.values()]
    signals.sort(key=lambda item: (item["referenceElementId"], item["termKey"]))
    return signals, {"openReferenceElements": len(open_refs), "openSubmissionTexts": len(open_subs), "signals": len(signals)}


def run_signals(store, reference_key):
    bundle = store.snapshot()
    source = next((model["source"] for model in bundle["models"]
                   if model["source"]["key"] == reference_key and model["source"]["role"] == "reference"), None)
    if source is None:
        raise ValueError("REFERENCE_KEY must select exactly one reference from the snapshot")
    candidates = _result(store.read(f"candidates/{reference_key}.json"), SERVICE, "semantic-candidates/v1")
    comparison = _result(store.read(f"comparisons/{reference_key}.json"), "one-to-one-graph-matching", "reference-comparison/v2")
    if (comparison["candidateHash"] != candidates["candidateHash"] or comparison["inputHash"] != bundle["inputHash"]
            or candidates["inputHash"] != bundle["inputHash"]):
        raise ValueError("comparison and candidates do not belong to the frozen input")
    graphs = {side: _Graph(_result(store.read(f"graphs/{key}.json"), "graph-parser", "graph-result/v1")["graph"])
              for side, key in (("student", "submission"), ("reference", reference_key))}
    inventories = {side: _result(store.read(f"labels/{key}.json"), "model-label-extraction", "element-inventory/v1")
                   for side, key in (("student", "submission"), ("reference", reference_key))}
    graph_matching = bundle["comparisonConfig"].get("graphMatching", {})
    signals, coverage = build_signals(candidates, comparison, graphs, inventories, graph_matching)
    producer = producer_metadata()
    result = {
        "schema": "synonym-signals/v1", "evaluationId": bundle["evaluationId"], "inputHash": bundle["inputHash"],
        "candidateHash": candidates["candidateHash"], "comparisonHash": comparison["comparisonHash"],
        "reference": {"key": reference_key, "modelId": source["modelId"], "versionId": source["versionId"]},
        "producer": {key: producer[key] for key in ("service", "version", "resourceHash")},
        "glossaryRevision": graph_matching.get("glossaries", {}).get(reference_key, {}).get("revision", 0),
        "termNormalization": TERM_NORMALIZATION, "coverage": coverage, "signals": signals,
    }
    return {"schema": "workflow-result/v1", "schemaVersion": 1, "status": "ok", "capability": "synonym-signals",
            "mode": "signals", "summary": f"{coverage['signals']} signals for {coverage['openReferenceElements']} open reference elements",
            "result": result}
