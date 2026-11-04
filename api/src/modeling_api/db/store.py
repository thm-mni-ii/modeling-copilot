"""Kleine, wiederverwendbare MongoDB-Helfer.

Hier liegt bewusst alles an einem Ort: IDs erzeugen, Dokumente wandeln,
einzelne Dokumente laden, Listen mit skip/limit blättern und neue Versionen
konfliktsicher anhängen.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pymongo.asynchronous.collection import AsyncCollection
from pymongo.errors import DuplicateKeyError

from modeling_api.core.errors import conflict, not_found

Document = dict[str, Any]


def new_id() -> str:
    """Lokale IDs sind UUID-Strings; in MongoDB werden sie als _id gespeichert."""
    return str(uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


def to_api(document: Document) -> Document:
    """Wandelt _id in id um, damit das JSON-Schema zur API passt."""
    return {"id": str(document["_id"]), **{k: v for k, v in document.items() if k != "_id"}}


async def get_or_404(collection: AsyncCollection, document_id: str) -> Document:
    """Lädt ein Dokument oder wirft 404."""
    result = await collection.find_one({"_id": document_id})
    if result is None:
        raise not_found()
    return to_api(result)


async def insert(collection: AsyncCollection, fields: Document) -> Document:
    """Fügt ein Dokument mit frischer ID und Zeitstempel ein."""
    document = {"_id": new_id(), "createdAt": utcnow(), **fields}
    await collection.insert_one(document)
    return to_api(document)


def sort_stages(field: str, *, descending: bool = True, identifier_desc: bool = True) -> list[Document]:
    """Sort names naturally without changing query or lookup equality semantics."""
    direction = -1 if descending else 1
    identifiers = -1 if identifier_desc else 1
    if field != "name":
        return [{"$sort": {field: direction, "_id": identifiers}}]

    # Names have at most 256 characters. Equal-width digit runs sort numerically,
    # including numbers too large for MongoDB's numeric types and leading zeros.
    key = "_naturalNameSortKey"
    return [
        {"$set": {key: {"$reduce": {
            "input": {"$regexFindAll": {"input": {"$ifNull": ["$name", ""]}, "regex": "[0-9]+|[^0-9]+"}},
            "initialValue": "",
            "in": {"$concat": ["$$value", {"$cond": [
                {"$regexMatch": {"input": "$$this.match", "regex": "^[0-9]"}},
                {"$concat": [
                    {"$substrCP": ["0" * 256, 0, {"$subtract": [256, {"$strLenCP": "$$this.match"}]}]},
                    "$$this.match",
                ]},
                "$$this.match",
            ]}]},
        }}}},
        {"$sort": {key: direction, "_id": identifiers}},
        {"$unset": key},
    ]


async def list_page(
    collection: AsyncCollection,
    filters: Document,
    skip: int,
    limit: int,
    *,
    sort_field: str = "createdAt",
    sort_desc: bool = True,
    omit: tuple[str, ...] = (),
) -> Document:
    """Einfaches Blättern: skip Einträge überspringen, limit zurückgeben.

    Antwortform: {"items": [...], "total": Gesamtanzahl}. Große Inhaltsfelder
    (z. B. data) können über omit weggelassen werden.
    """
    projection = {field: 0 for field in omit} if omit else None
    total = await collection.count_documents(filters)
    if sort_field == "name":
        pipeline = [
            {"$match": filters},
            *sort_stages(sort_field, descending=sort_desc),
            {"$skip": skip},
            {"$limit": limit},
        ]
        if projection:
            pipeline.append({"$project": projection})
        cursor = await collection.aggregate(pipeline)
        return {"items": [to_api(document) async for document in cursor], "total": total}
    cursor = (
        collection.find(filters, projection)
        .sort([(sort_field, -1 if sort_desc else 1), ("_id", -1)])
        .skip(skip)
        .limit(limit)
    )
    items = [to_api(document) async for document in cursor]
    return {"items": items, "total": total}


async def save_version(
    identities: AsyncCollection,
    versions: AsyncCollection,
    parent_field: str,
    parent_id: str,
    base_version_id: str | None,
    user_id: str,
    fields: Document,
) -> Document:
    """Hängt eine neue Version an ein Objekt an (Sprache, Aufgabe oder Modell).

    Ablauf ohne Transaktion, aber konfliktsicher:
    1. Prüfen, dass base_version_id noch der aktuelle Stand ist.
    2. Version mit der gemeinsamen Checkpoint-/Release-Nummer einfügen.
    3. latestVersionId nur dann tauschen, wenn sich seit Schritt 1 nichts
       geändert hat (ein einzelnes Update ist in MongoDB atomar).
       War ein paralleler Request schneller, wird die eigene Version wieder
       entfernt und der Client bekommt 409.
    """
    parent = await identities.find_one({"_id": parent_id})
    if parent is None:
        raise not_found()
    if parent["latestVersionId"] != base_version_id:
        raise conflict()

    previous = await versions.find_one({"_id": base_version_id}) if base_version_id else None
    number = next_version_number(previous.get("versionNumber") if previous else None, fields.get("kind"))
    version = {
        "_id": new_id(),
        parent_field: parent_id,
        "versionNumber": number,
        "createdBy": user_id,
        "createdAt": utcnow(),
        **fields,
    }
    try:
        await versions.insert_one(version)
    except DuplicateKeyError:
        # Zwei parallele Requests haben dieselbe Versionsnummer gezogen.
        raise conflict() from None

    updated = await identities.update_one(
        {"_id": parent_id, "latestVersionId": base_version_id},
        {"$set": {"latestVersionId": version["_id"]}},
    )
    if updated.matched_count == 0:
        await versions.delete_one({"_id": version["_id"]})
        raise conflict()
    return to_api(version)


def next_version_number(previous: object, kind: object) -> str:
    """Calculates semantic save numbers shared by models, languages and tasks."""
    raw = str(previous or "0.0")
    try:
        major, minor = (int(part) for part in (raw.split(".", 1) + ["0"])[:2])
    except ValueError:
        major, minor = 0, 0

    if kind == "checkpoint":
        return f"{max(major, 1)}.{minor + 1}"
    return f"{major + 1}.0"
