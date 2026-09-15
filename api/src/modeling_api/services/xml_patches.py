"""Small, deliberately restricted XML-patch profile for model Cells."""

from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from re import fullmatch

from lxml import etree

from modeling_api.core.errors import ApiError

PATCH_NAMESPACE = "urn:ietf:rfc:7351"
_PATCH_TAG = f"{{{PATCH_NAMESPACE}}}patch"
_CELL_SELECTOR = r"/?GraphDataModel/root/Cell\[@id=(['\"])([^'\"]+)\1\]"


def _invalid(message: str) -> ApiError:
    return ApiError(422, "INVALID_MODEL_PATCH", message)


def _parse(xml: str, *, patch: bool = False) -> etree._Element:
    try:
        parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)
        return etree.fromstring(xml.encode("utf-8"), parser=parser)
    except (etree.XMLSyntaxError, ValueError) as exc:
        kind = "Patch" if patch else "Modell-XML"
        raise _invalid(f"{kind} ist nicht wohlgeformt.") from exc


def validate_model_xml(xml: str) -> etree._Element:
    root = _parse(xml)
    if root.tag != "GraphDataModel":
        raise _invalid("Das Wurzelelement muss GraphDataModel sein.")
    ids: set[str] = set()
    cells = root.xpath("./root/Cell")
    if not cells:
        raise _invalid("Das Modell enthält keine Cells.")
    for cell in cells:
        cell_id = (cell.get("id") or "").strip()
        if not cell_id:
            raise _invalid("Jede Cell benötigt eine nicht leere ID.")
        if cell_id in ids:
            raise _invalid(f"Die Cell-ID {cell_id!r} ist nicht eindeutig.")
        ids.add(cell_id)
    return root


def _selector_id(selector: str) -> str:
    match = fullmatch(_CELL_SELECTOR, selector)
    if not match:
        raise _invalid("Patch-Selektoren dürfen nur eine Cell über ihre ID adressieren.")
    return match.group(2)


def _target(root: etree._Element, cell_id: str) -> etree._Element:
    matches = root.xpath("./root/Cell[@id=$cell_id]", cell_id=cell_id)
    if len(matches) != 1:
        raise _invalid(f"Patch-Ziel {cell_id!r} ist nicht eindeutig vorhanden.")
    return matches[0]


def apply_patch(model_root: etree._Element, patch_xml: str) -> None:
    patch_root = _parse(patch_xml, patch=True)
    if patch_root.tag != _PATCH_TAG:
        raise _invalid("Das Patch-Wurzelelement muss p:patch sein.")

    model_container = model_root.find("root")
    if model_container is None:
        raise _invalid("GraphDataModel/root fehlt.")

    for operation in patch_root:
        if operation.tag == f"{{{PATCH_NAMESPACE}}}add":
            if operation.get("sel", "").lstrip("/") != "GraphDataModel/root":
                raise _invalid("add darf nur an GraphDataModel/root anhängen.")
            if operation.get("pos", "append") != "append":
                raise _invalid("add unterstützt nur pos='append'.")
            children = list(operation)
            if len(children) != 1 or children[0].tag != "Cell":
                raise _invalid("add muss genau eine Cell enthalten.")
            cell = deepcopy(children[0])
            cell_id = (cell.get("id") or "").strip()
            if not cell_id or model_root.xpath("./root/Cell[@id=$cell_id]", cell_id=cell_id):
                raise _invalid("Die hinzugefügte Cell benötigt eine neue, eindeutige ID.")
            model_container.append(cell)
            continue

        if operation.tag not in {
            f"{{{PATCH_NAMESPACE}}}remove",
            f"{{{PATCH_NAMESPACE}}}replace",
        }:
            raise _invalid("Nur add, remove und replace werden unterstützt.")

        cell_id = _selector_id(operation.get("sel", ""))
        target = _target(model_root, cell_id)
        if operation.tag == f"{{{PATCH_NAMESPACE}}}remove":
            if list(operation):
                raise _invalid("remove darf keinen Inhalt besitzen.")
            target.getparent().remove(target)
            continue

        children = list(operation)
        if len(children) != 1 or children[0].tag != "Cell":
            raise _invalid("replace muss genau eine Cell enthalten.")
        replacement = deepcopy(children[0])
        if replacement.get("id") != cell_id:
            raise _invalid("replace darf die Cell-ID nicht verändern.")
        target.getparent().replace(target, replacement)


def apply_patches(base_xml: str, patch_xml_documents: Iterable[str]) -> str:
    root = validate_model_xml(base_xml)
    for patch_xml in patch_xml_documents:
        apply_patch(root, patch_xml)
    validate_model_xml(etree.tostring(root, encoding="unicode"))
    return etree.tostring(root, encoding="unicode")
