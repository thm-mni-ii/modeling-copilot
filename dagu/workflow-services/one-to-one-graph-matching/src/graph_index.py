"""Derived indices for graph-result/v3, preserving its original relations."""

from collections import defaultdict
import json


class GraphIndex:
    def __init__(self, graph):
        if (not isinstance(graph, dict) or type(graph.get("schemaVersion")) is not int
                or graph["schemaVersion"] != 3
                or any(not isinstance(graph.get(key), list) for key in ("nodes", "edges", "languages"))):
            raise ValueError("graph must contain schemaVersion=3 and nodes/edges/languages arrays")
        self.nodes = {}
        self.by_kind = defaultdict(list)
        self.by_type = defaultdict(list)
        self.by_group = defaultdict(list)
        self.by_definition = defaultdict(list)
        self.incoming = defaultdict(list)
        self.outgoing = defaultdict(list)
        self.parents = defaultdict(list)
        self.children = defaultdict(list)
        self.endpoints = defaultdict(dict)
        seen_edges = set()
        for node in graph["nodes"]:
            if not isinstance(node, dict):
                raise ValueError("graph node must be an object")
            identity = node.get("id")
            if not isinstance(identity, str) or not identity.strip() or identity in self.nodes:
                raise ValueError("graph node IDs must be unique non-empty strings")
            if node.get("kind") not in ("modelElement", "structuralElement", "connection", "connectionLabel", None):
                raise ValueError("invalid graph node kind")
            if node.get("comparisonRole") not in ("semantic", "structural", "unsupported"):
                raise ValueError("invalid graph node comparisonRole")
            for key in ("type", "kind", "comparisonGroup", "language", "definition", "languageResolution"):
                if key not in node:
                    raise ValueError(f"graph node missing {key}")
            if any(node[key] is not None and not isinstance(node[key], str) for key in ("type", "comparisonGroup")):
                raise ValueError("graph node type and comparisonGroup must be strings or null")
            language = node["language"]
            if language is not None and (
                not isinstance(language, dict)
                or any(not isinstance(language.get(key), str) or not language[key]
                       for key in ("languageId", "versionId"))
            ):
                raise ValueError("graph node language needs languageId and versionId")
            if node["languageResolution"] not in ("resolved", "ambiguous", "unresolved"):
                raise ValueError("invalid graph node languageResolution")
            definition = node["definition"]
            if definition is not None and not isinstance(definition, dict):
                raise ValueError("graph node definition must be an object or null")
            self.nodes[identity] = node
            self.by_kind[node["kind"]].append(identity)
            self.by_type[node["type"]].append(identity)
            self.by_group[node["comparisonGroup"]].append(identity)
            if definition is not None:
                self.by_definition[json.dumps(definition, sort_keys=True, ensure_ascii=False)].append(identity)

        seen_ids = set(self.nodes)
        for edge in graph["edges"]:
            if not isinstance(edge, dict) or edge.get("kind") not in ("contains", "endpoint"):
                raise ValueError("invalid graph edge")
            edge_id = edge.get("id")
            if edge_id is not None:
                if not isinstance(edge_id, str) or not edge_id.strip() or edge_id in seen_ids:
                    raise ValueError("graph cell IDs must be unique non-empty strings")
                seen_ids.add(edge_id)
            if any(key not in edge for key in ("source", "target", "role")):
                raise ValueError("graph edges need source, target and role")
            source, target, role = edge["source"], edge["target"], edge["role"]
            if any(value is not None and not isinstance(value, str) for value in (source, target, role)):
                raise ValueError("graph edge references and role must be strings or null")
            key = (edge["kind"], source, target, role)
            if key in seen_edges:
                raise ValueError("duplicate graph edge")
            seen_edges.add(key)
            if source is not None and source not in self.nodes or target is not None and target not in self.nodes:
                raise ValueError("graph edge refers to an unknown node")
            if source is not None:
                self.outgoing[source].append(edge)
            if target is not None:
                self.incoming[target].append(edge)
            if edge["kind"] == "contains":
                if source is None or target is None:
                    raise ValueError("contains edges need both endpoints")
                self.parents[source].append(edge)
                self.children[target].append(edge)
            else:
                if role not in ("source", "target"):
                    raise ValueError("endpoint edges need a source or target role")
                connection = target if role == "source" else source
                terminal = source if role == "source" else target
                if connection is None or self.nodes[connection]["kind"] != "connection":
                    raise ValueError("endpoint edge must refer to a connection node")
                if role in self.endpoints[connection]:
                    raise ValueError("connection has duplicate endpoint role")
                self.endpoints[connection][role] = terminal

    def owner(self, identity):
        """Return the nearest semantic parent if the retained path is unambiguous."""
        visited = {identity}
        current = identity
        while True:
            edges = self.parents[current]
            if len(edges) != 1:
                return None
            current = edges[0]["target"]
            if current in visited:
                return None
            visited.add(current)
            node = self.nodes[current]
            if node["kind"] != "structuralElement":
                return current
