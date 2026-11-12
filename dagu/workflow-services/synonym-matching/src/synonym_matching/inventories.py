"""Validate the existing V2 inventory contract without re-extracting any elements."""

import json

import jsonschema

from workflow_io import identifier
from .provenance import SERVICE_ROOT, content_hash


def validate_inventory(envelope, side):
    if type(envelope["schemaVersion"]) is not int:
        raise ValueError("inventory envelope schemaVersion must be the integer 1")
    data = envelope["result"]
    identifier(data["evaluationId"])
    source = data["source"]
    identifier(source["key"])
    expected_role = "submission" if side == "student" else "reference"
    if source["role"] != expected_role or (source["key"] == "submission") != (side == "student"):
        raise ValueError(f"{side} inventory has the wrong source role/key")
    if data["inventoryHash"] != content_hash({key: value for key, value in data.items() if key != "inventoryHash"}):
        raise ValueError(f"{side} inventory hash does not match its V2 content")
    seen = set()
    for element in data["elements"]:
        identity = element["id"]
        if not identity.strip() or identity in seen:
            raise ValueError(f"{side} inventory needs unique non-empty element IDs")
        seen.add(identity)
        status, text = element["labelStatus"], element["matchText"]
        if (status == "present") != bool(text.strip()):
            raise ValueError(f"{side} element {identity}: labelStatus conflicts with matchText")
        language = element["textLanguage"]
        if language is not None and not language.strip():
            raise ValueError(f"{side} element {identity}: textLanguage must be non-empty or null")
    for text in data["connectionTexts"]:
        identity = text["id"]
        if not identity.strip() or identity in seen:
            raise ValueError(f"{side} inventory needs unique non-empty graph-cell IDs")
        seen.add(identity)
        status, value = text["labelStatus"], text["matchText"]
        if (status == "present") != bool(value.strip()):
            raise ValueError(f"{side} connection text {identity}: labelStatus conflicts with matchText")
        if text["kind"] == "additionalLabel" and not text["connectionLabelId"]:
            raise ValueError(f"{side} connection text {identity}: additional labels need connectionLabelId")
    return data


def read_pair(payload, bundle=None, reference_key=None):
    schema = json.loads((SERVICE_ROOT / "schemas/input.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(payload, schema)
    inventories = {side: validate_inventory(payload[f"{side}Inventory"], side) for side in ("student", "reference")}
    student, reference = inventories["student"], inventories["reference"]
    if student["evaluationId"] != reference["evaluationId"] or student["inputHash"] != reference["inputHash"]:
        raise ValueError("both inventories must belong to the same evaluation input")
    if bundle is not None:
        if payload.get("comparisonConfig", {}) != bundle["comparisonConfig"]:
            raise ValueError("comparisonConfig differs from the frozen snapshot")
        if reference["source"]["key"] != reference_key:
            raise ValueError("reference inventory does not match REFERENCE_KEY")
        for data in inventories.values():
            if data["evaluationId"] != bundle["evaluationId"] or data["inputHash"] != bundle["inputHash"]:
                raise ValueError("inventory does not belong to the frozen evaluation input")
            models = [model for model in bundle["models"] if model["source"]["key"] == data["source"]["key"]]
            if len(models) != 1 or models[0]["source"] != data["source"]:
                raise ValueError("inventory source does not match the frozen model source")
    return inventories
