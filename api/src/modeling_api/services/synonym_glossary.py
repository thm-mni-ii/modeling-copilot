"""Per-solution synonym glossary: administrator decisions, validation and evaluation freeze."""

import re
import unicodedata
import xml.etree.ElementTree as ET
from uuid import UUID

from pymongo.errors import DuplicateKeyError

from modeling_api.core.auth import User
from modeling_api.core.errors import ApiError, conflict, not_found
from modeling_api.db.client import db
from modeling_api.db.store import Document, new_id, to_api, utcnow
from modeling_api.schemas.synonym_glossary import ImportGlossaryEntries, SaveGlossaryEntries, SetMatchingSource
from modeling_api.services import languages
from modeling_api.services.models import _materialize_version
from modeling_api.services.tasks import get_sample_solution

# Mirrors dagu/workflow-services/synonym-matching/src/synonym_matching/term_key.py.
TERM_NORMALIZATION = "nfc-casefold-space-v1"
_FORMATTING_TAG = re.compile(r"</?(?P<tag>b|strong|i|em|u|br|div)\s*/?>", re.IGNORECASE)


def term_key(text: str) -> str:
    collapsed = " ".join(unicodedata.normalize("NFC", text).split())
    return unicodedata.normalize("NFC", collapsed.casefold()).rstrip(" .:,;")


def require_admin(user: User) -> None:
    if not user.is_admin:
        raise ApiError(403, "FORBIDDEN", "Administrator access is required.")


def _flag(value: object) -> bool:
    return value in ("true", "1")


def _object_field(cell: ET.Element, name: str) -> dict:
    return next((dict(child.attrib) for child in cell if child.get("as") == name), {})


def _type_of(cell: ET.Element) -> str:
    if _flag(cell.get("edge")):
        return cell.get("connectionId", "")
    if cell.get("connectionLabelId") is not None:
        return cell.get("connectionLabelId", "")
    return cell.get("diagramElementType") or _object_field(cell, "diagramAttributes").get("type") or ""


def _roles(cell: ET.Element) -> tuple:
    style = dict(part.split("=", 1) for part in cell.get("style", "").split(";") if "=" in part)
    style.update(_object_field(cell, "style"))
    return cell.get("cellRole"), cell.get("canvasRole"), style.get("cellRole")


def _label_text(label: str) -> str:
    """Same text projection as the label-extraction service, so label comparisons agree with the matcher."""
    parts: list[str] = []
    position, block_boundary = 0, False

    def append_text(text: str) -> None:
        nonlocal block_boundary
        if text:
            if block_boundary and parts and not parts[-1].endswith("\n") and not text.startswith("\n"):
                parts.append("\n")
            parts.append(text)
            block_boundary = False

    for match in _FORMATTING_TAG.finditer(label):
        append_text(label[position:match.start()])
        tag = match.group("tag").lower()
        if tag == "br":
            if block_boundary and parts and not parts[-1].endswith("\n"):
                parts.append("\n")
            parts.append("\n")
            block_boundary = False
        elif tag == "div":
            block_boundary = True
        position = match.end()
    append_text(label[position:])
    return "".join(parts)


def _definitions(language_versions: list[Document]) -> tuple[dict, dict, set, set, dict]:
    elements: dict = {}
    connections: dict = {}
    feedback_elements: set = set()
    feedback_connections: set = set()
    groups: dict = {}

    def register(items: list, catalog: dict, path: str, key: tuple, nested: bool = False) -> None:
        for index, item in enumerate(items):
            item_path = f"{path}/{index}"
            catalog.setdefault(item["type"], []).append((key, item_path, item))
            if nested:
                register(item.get("children", []), catalog, f"{item_path}/children", key, True)

    for version in language_versions:
        key = (version["languageId"], version["id"])
        data = version["data"]
        register(data.get("elements", []), elements, "/elements", key, True)
        register(data.get("connections", []), connections, "/connections", key)
        for index, connection in enumerate(data.get("connections", [])):
            register(connection.get("additionalLabels", []), elements, f"/connections/{index}/additionalLabels", key)
        for group in data.get("evaluation", {}).get("comparisonGroups", []):
            for field, category in (("elementTypes", "element"), ("connectionTypes", "connection")):
                for type_name in group.get(field, []):
                    groups.setdefault((category, *key, type_name), set()).add(group["id"])
        for entry in data.get("feedback", {}).get("canvas", {}).get("configurableElements", []):
            for field, target in (("element", feedback_elements), ("connection", feedback_connections)):
                if entry.get(field, {}).get("type") is not None:
                    target.add(entry[field]["type"])
    return elements, connections, feedback_elements, feedback_connections, groups


def comparable_elements(xml: str, language_versions: list[Document]) -> dict[str, Document]:
    """Elements and connections the graph parser classifies as semantic and that carry their own text."""
    if "<!DOCTYPE" in xml.upper() or "<!ENTITY" in xml.upper():
        raise ApiError(422, "INVALID_MODEL", "The sample solution cannot be read.")
    try:
        root_node = ET.fromstring(xml).find("root")
    except ET.ParseError as error:
        raise ApiError(422, "INVALID_MODEL", "The sample solution cannot be read.") from error
    if root_node is None:
        raise ApiError(422, "INVALID_MODEL", "The sample solution cannot be read.")
    cells = {cell.get("id"): cell for cell in root_node if cell.tag == "Cell" and cell.get("id")}
    children: dict = {}
    for identity, cell in cells.items():
        children.setdefault(cell.get("parent"), []).append(identity)
    roots = children.get(None, [])
    layers = children.get(roots[0], []) if len(roots) == 1 else []
    if len(layers) < 2:
        raise ApiError(422, "INVALID_MODEL", "The sample solution has no modeling layer.")
    modeling_layer = layers[0]
    scope: set = set()
    pending = list(children.get(modeling_layer, []))
    while pending:
        identity = pending.pop()
        if identity not in scope:
            scope.add(identity)
            pending.extend(children.get(identity, []))
    elements, connections, feedback_elements, feedback_connections, groups = _definitions(language_versions)
    excluded = set(cells) - scope
    for identity in scope:
        cell = cells[identity]
        edge = _flag(cell.get("edge"))
        cell_type = _type_of(cell)
        feedback_type = (cell_type in (feedback_connections if edge else feedback_elements)
                         or cell_type == "__feedback_note_link__") and cell_type not in (connections if edge else elements)
        if "feedback" in _roles(cell) or feedback_type:
            excluded.add(identity)
    changed = True
    while changed:
        changed = False
        for identity, cell in cells.items():
            if identity not in excluded and ((cell.get("parent") != modeling_layer and cell.get("parent") in excluded)
                                             or (_flag(cell.get("edge")) and any(cell.get(end) in excluded for end in ("source", "target")))):
                excluded.add(identity)
                changed = True
    model_cells = {identity: cell for identity, cell in cells.items() if identity not in excluded}
    parents = {identity: None if cell.get("parent") == modeling_layer else cell.get("parent")
               for identity, cell in model_cells.items()}
    known = {(version["languageId"], version["id"]) for version in language_versions}
    resolved: dict = {}
    result: dict[str, Document] = {}
    order: list = []
    pending = sorted(identity for identity in model_cells if parents[identity] not in model_cells)
    while pending:
        identity = pending.pop()
        order.append(identity)
        pending.extend(sorted(child for child in children.get(identity, []) if child in model_cells))
    for identity in order:
        cell = model_cells[identity]
        edge = _flag(cell.get("edge"))
        is_label = cell.get("connectionLabelId") is not None
        cell_type = _type_of(cell)
        available = [entry for entry in (connections if edge else elements).get(cell_type, [])
                     if ("/additionalLabels/" in entry[1]) == is_label]
        attributes = _object_field(cell, "diagramAttributes")
        pinned = (cell.get("languageId", attributes.get("languageId")), cell.get("languageVersionId", attributes.get("languageVersionId")))
        if pinned in known:
            available = [entry for entry in available if entry[0] == pinned]
        independent = [entry for entry in available if "/children/" not in entry[1] and "/additionalLabels/" not in entry[1]]
        parent = resolved.get(parents[identity])
        contextual = [entry for entry in available if parent and entry[0] == parent[0]
                      and entry[1].rsplit("/", 2)[0] == parent[1] and entry[1].rsplit("/", 2)[1] in ("children", "additionalLabels")]
        candidates = contextual or independent
        entry = candidates[0] if len(candidates) == 1 else None
        resolved[identity] = entry
        kind = ("connection" if edge else None if is_label or contextual or (available and not independent)
                else "element" if cell_type else None)
        origins = {candidate[0] for candidate in (candidates or available)}
        language = next(iter(origins)) if len(origins) == 1 else pinned if pinned in known else None
        role = cell.get("comparisonRole", attributes.get("comparisonRole")) or (entry[2].get("comparisonRole") if entry else None)
        label = _label_text(cell.get("value", attributes.get("label", "")))
        if kind is None or entry is None or language is None or role == "structural" or not label.strip():
            continue
        group_ids = groups.get((kind, *language, cell_type), set())
        result[identity] = {"id": identity, "label": label, "targetKind": kind, "type": cell_type or None,
                            "comparisonGroup": next(iter(group_ids)) if len(group_ids) == 1 else None}
    return result


async def language_versions(references: list[Document]) -> list[Document]:
    collected: dict[tuple[str, str], Document] = {}
    pending = list(references)
    while pending:
        reference = pending.pop()
        key = (reference["languageId"], reference["versionId"])
        if key in collected:
            continue
        if len(collected) >= languages.MAX_LANGUAGE_REFS:
            raise ApiError(422, "TOO_MANY_REFERENCES", "Too many included language versions.")
        version = await languages.get_version(UUID(key[0]), UUID(key[1]))
        collected[key] = {**version, "languageId": key[0]}
        pending.extend(version.get("includedLanguageVersions", []))
    return list(collected.values())


async def solution_elements(solution: Document) -> dict[str, Document]:
    return comparable_elements(solution["data"]["xml"], await language_versions(solution["workspaceLanguages"]))


def scope_of(task_id: UUID, model_id: UUID, model_version_id: UUID) -> Document:
    return {"taskId": str(task_id), "referenceModelId": str(model_id), "referenceVersionId": str(model_version_id)}


async def list_tasks() -> list[Document]:
    tasks = await db.task.find({"archivedAt": None}, {"name": 1}).sort("name", 1).to_list(None)
    releases = await db.task_version.find(
        {"taskId": {"$in": [task["_id"] for task in tasks]}, "kind": "release", "data.sampleSolutions.0": {"$exists": True}},
        {"taskId": 1, "versionNumber": 1, "data.sampleSolutions": 1},
    ).sort("versionNumber", -1).to_list(None)
    by_task: dict[str, list[Document]] = {}
    for release in releases:
        by_task.setdefault(release["taskId"], []).append({
            "id": release["_id"], "versionNumber": release["versionNumber"],
            "sampleSolutions": [{"modelId": item["modelId"], "versionId": item["versionId"]}
                                for item in release["data"]["sampleSolutions"]],
        })
    return [{"id": task["_id"], "name": task["name"], "releases": by_task[task["_id"]]}
            for task in tasks if task["_id"] in by_task]


async def _commit(scope: Document, base_revision: int, entries: list[Document], log: list[Document]) -> None:
    """Compare-and-set on the revision; the first write inserts, guarded by the unique scope index."""
    now = utcnow()
    try:
        result = await db.synonym_glossaries.update_one(
            {**scope, "revision": base_revision},
            {"$set": {"revision": base_revision + 1, "entries": entries, "updatedAt": now},
             "$push": {"changes": {"$each": log}},
             "$setOnInsert": {"_id": new_id(), "createdAt": now}},
            upsert=base_revision == 0,
        )
    except DuplicateKeyError as error:
        raise conflict() from error
    if not result.matched_count and result.upserted_id is None:
        raise conflict()


async def _is_suggested(scope: Document, reference_element_id: str, key: str) -> bool:
    return await db.synonym_signal_sets.count_documents(
        {"referenceVersionId": scope["referenceVersionId"],
         "signals": {"$elemMatch": {"referenceElementId": reference_element_id, "termKey": key}}}, limit=1) > 0


async def save_entries(task_id: UUID, version_id: UUID, model_id: UUID, model_version_id: UUID,
                       body: SaveGlossaryEntries, user: User) -> None:
    solution = await get_sample_solution(task_id, version_id, model_id, model_version_id, user)
    elements = await solution_elements(solution)
    scope = scope_of(task_id, model_id, model_version_id)
    document = await db.synonym_glossaries.find_one(scope, {"revision": 1, "entries": 1})
    if (document["revision"] if document else 0) != body.base_revision:
        raise conflict()
    entries = {(item["referenceElementId"], item["termKey"]): item for item in (document or {}).get("entries", [])}
    revision, now, log = body.base_revision + 1, utcnow(), []
    for change in body.changes:
        element = elements.get(change.reference_element_id)
        if element is None:
            raise ApiError(422, "GLOSSARY_ELEMENT_NOT_COMPARABLE", "This element is not comparable in the sample solution.")
        key = term_key(change.term)
        if not key:
            raise ApiError(422, "GLOSSARY_TERM_EMPTY", "The term has no comparable text.")
        if key == term_key(element["label"]):
            raise ApiError(422, "GLOSSARY_TERM_IS_LABEL", "The term equals the label of this element.")
        pair = (change.reference_element_id, key)
        before = entries.get(pair)
        if (before["status"] if before else None) == change.status:
            continue
        if change.status is None:
            del entries[pair]
        elif before:
            entries[pair] = {**before, "status": change.status, "matchingSource": False,
                             "updatedBy": user.id, "updatedAt": now}
        else:
            entries[pair] = {"id": new_id(), "referenceElementId": change.reference_element_id, "term": change.term.strip(),
                             "termKey": key, "status": change.status, "matchingSource": False,
                             "origin": "suggestion" if await _is_suggested(scope, *pair) else "manual",
                             "createdBy": user.id, "createdAt": now, "updatedBy": user.id, "updatedAt": now}
        log.append({"revision": revision, "referenceElementId": change.reference_element_id, "termKey": key,
                    "before": before["status"] if before else None, "after": change.status, "by": user.id, "at": now})
    if log:
        await _commit(scope, body.base_revision, list(entries.values()), log)


async def set_matching_source(task_id: UUID, version_id: UUID, model_id: UUID, model_version_id: UUID,
                               entry_id: UUID, body: SetMatchingSource, user: User) -> None:
    require_admin(user)
    solution = await get_sample_solution(task_id, version_id, model_id, model_version_id, user)
    elements = await solution_elements(solution)
    scope = scope_of(task_id, model_id, model_version_id)
    document = await db.synonym_glossaries.find_one(scope, {"revision": 1, "entries": 1})
    if (document or {}).get("revision", 0) != body.base_revision:
        raise conflict()
    entries = (document or {}).get("entries", [])
    entry = next((item for item in entries if item["id"] == str(entry_id)), None)
    if entry is None or entry["referenceElementId"] not in elements:
        raise not_found()
    if body.enabled:
        if entry["status"] != "accepted":
            raise ApiError(422, "MATCHING_SOURCE_NOT_ACCEPTED", "Accept the synonym before enabling it as a matching source.")
    before = entry.get("matchingSource", False)
    if before == body.enabled:
        return
    now = utcnow()
    entry.update(matchingSource=body.enabled, updatedBy=user.id, updatedAt=now)
    await _commit(scope, body.base_revision, entries, [{"revision": body.base_revision + 1,
        "referenceElementId": entry["referenceElementId"], "termKey": entry["termKey"], "before": entry["status"], "after": entry["status"],
        "matchingSourceBefore": before, "matchingSourceAfter": body.enabled, "by": user.id, "at": now}])


async def import_entries(task_id: UUID, version_id: UUID, model_id: UUID, model_version_id: UUID,
                         body: ImportGlossaryEntries, user: User) -> tuple[int, list[str]]:
    """Copy entries whose element and label are unchanged in this solution version; report the rest."""
    solution = await get_sample_solution(task_id, version_id, model_id, model_version_id, user)
    scope = scope_of(task_id, model_id, model_version_id)
    source = await db.synonym_glossaries.find_one(scope_of(task_id, model_id, body.from_reference_version_id))
    previous = await db.model_versions.find_one({"_id": str(body.from_reference_version_id), "modelId": str(model_id), "kind": "release"})
    if source is None or previous is None or body.from_reference_version_id == model_version_id:
        raise not_found()
    old_elements = await solution_elements(to_api(await _materialize_version(previous)))
    new_elements = await solution_elements(solution)
    document = await db.synonym_glossaries.find_one(scope, {"revision": 1, "entries": 1})
    if (document["revision"] if document else 0) != body.base_revision:
        raise conflict()
    entries = {(item["referenceElementId"], item["termKey"]): item for item in (document or {}).get("entries", [])}
    revision, now, log, skipped = body.base_revision + 1, utcnow(), [], []
    for item in source["entries"]:
        old, new = old_elements.get(item["referenceElementId"]), new_elements.get(item["referenceElementId"])
        pair = (item["referenceElementId"], item["termKey"])
        if old is None or new is None or old["label"] != new["label"] or old["targetKind"] != new["targetKind"] or pair in entries:
            skipped.append(item["term"])
            continue
        entries[pair] = {**item, "id": new_id(), "matchingSource": False,
                         "createdBy": user.id, "createdAt": now, "updatedBy": user.id, "updatedAt": now}
        log.append({"revision": revision, "referenceElementId": pair[0], "termKey": pair[1],
                    "before": None, "after": item["status"], "by": user.id, "at": now})
    if log:
        await _commit(scope, body.base_revision, list(entries.values()), log)
    return len(log), skipped


async def frozen_glossaries(task_id: str, references: list[Document]) -> Document:
    """The accepted and rejected decisions of each reference key at this moment; empty keys are omitted."""
    frozen: Document = {}
    for reference in references:
        document = await db.synonym_glossaries.find_one(
            {"taskId": task_id, "referenceModelId": reference["modelId"], "referenceVersionId": reference["versionId"]},
            {"revision": 1, "entries": 1})
        entries = sorted(({"referenceElementId": item["referenceElementId"], "termKey": item["termKey"], "status": item["status"],
                           **({"matchingSource": True, "term": item["term"]} if item.get("matchingSource") and item["status"] == "accepted" else {})}
                          for item in (document or {}).get("entries", []) if item["status"] != "ignored"),
                         key=lambda item: (item["referenceElementId"], item["termKey"]))
        if entries:
            frozen[reference["key"]] = {"revision": document["revision"], "termNormalization": TERM_NORMALIZATION, "entries": entries}
    return frozen
