"""Validation for task-edit documents stored on models."""

from copy import deepcopy
from datetime import datetime
from hashlib import sha256
from html.parser import HTMLParser
import json
import re
from typing import Any
from uuid import UUID

from modeling_api.core.errors import ApiError
from modeling_api.db.store import Document

EDIT_MARKS = {
    "taskEditHighlight": "highlight",
    "taskEditBold": "bold",
    "taskEditItalic": "italic",
    "taskEditUnderline": "underline",
    "taskEditStrike": "strike",
    "taskEditTextColor": "textColor",
    "taskEditInlineCode": "inlineCode",
    "taskEditInsertion": "insertion",
}
ALLOWED_NODES = {
    "doc", "paragraph", "text", "heading", "bulletList", "orderedList",
    "listItem", "blockquote", "codeBlock", "hardBreak", "horizontalRule",
}
ALLOWED_MARKS = {
    "bold", "italic", "underline", "strike", "code", "textStyle", "highlight",
    "taskElement", "taskConnection", *EDIT_MARKS,
}
TEXT_COLORS = {
    "#000000", "#424242", "#E53935", "#D81B60", "#8E24AA",
    "#1E88E5", "#00ACC1", "#43A047", "#FB8C00", "#FDD835",
}
HIGHLIGHT_COLORS = {"#FFF176", "#C8E6C9", "#BBDEFB", "#F8BBD0", "#FFE0B2", "#E1BEE7"}


class _OriginalHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.references: set[tuple[str, str, str]] = set()
        self.signature: list[tuple[object, ...]] = [("open", "doc", ())]
        self._active_marks: list[tuple[object, ...]] = []
        self._stack: list[tuple[str, str | None, list[tuple[object, ...]]]] = []
        self._at_text_block_start = False
        self._after_hard_break = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        node_type: str | None = None
        node_attrs: tuple[tuple[str, object], ...] = ()
        structural = {
            "p": "paragraph", "ul": "bulletList", "ol": "orderedList", "li": "listItem",
            "blockquote": "blockquote", "pre": "codeBlock",
        }
        if tag in structural:
            node_type = structural[tag]
            if tag == "ol":
                node_attrs = (("start", int(values.get("start") or 1)),)
            elif tag == "p":
                align = _style_value(values.get("style"), "text-align")
                node_attrs = (("textAlign", align),) if align else ()
        elif tag in {"h1", "h2", "h3"}:
            node_type = "heading"
            align = _style_value(values.get("style"), "text-align")
            heading_attrs: list[tuple[str, object]] = [("level", int(tag[1]))]
            if align:
                heading_attrs.append(("textAlign", align))
            node_attrs = tuple(heading_attrs)
        elif tag == "br":
            self.signature.append(("leaf", "hardBreak", ()))
            self._after_hard_break = True
            return
        elif tag == "hr":
            self.signature.append(("leaf", "horizontalRule", ()))
            return

        marks: list[tuple[object, ...]] = []
        if tag in {"strong", "b"}:
            marks.append(("bold",))
        elif tag in {"em", "i"}:
            marks.append(("italic",))
        elif tag == "u":
            marks.append(("underline",))
        elif tag in {"s", "strike", "del"}:
            marks.append(("strike",))
        elif tag == "code" and not any(entry[0] == "pre" for entry in self._stack):
            marks.append(("code",))

        language_id = values.get("data-task-element-language-id")
        element_type = values.get("data-task-element-type")
        if language_id and element_type:
            self.references.add(("element", language_id, element_type))
            marks.append(("taskElement", language_id, element_type))
        language_id = values.get("data-task-connection-language-id")
        connection_type = values.get("data-task-connection-type")
        if language_id and connection_type:
            self.references.add(("connection", language_id, connection_type))
            marks.append(("taskConnection", language_id, connection_type))
        color = _style_value(values.get("style"), "color")
        if color and color != "inherit":
            marks.append(("textStyle", "color", color.upper()))
        highlight = values.get("data-color") if tag == "mark" else _style_value(values.get("style"), "background-color")
        if highlight:
            marks.append(("highlight", "color", highlight.upper()))

        if node_type:
            self.signature.append(("open", node_type, tuple(sorted(node_attrs))))
            if node_type in {"paragraph", "heading", "codeBlock"}:
                self._at_text_block_start = True
        self._active_marks.extend(marks)
        self._stack.append((tag, node_type, marks))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in {"br", "hr"}:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if not self._stack:
            return
        _open_tag, node_type, marks = self._stack.pop()
        for mark in reversed(marks):
            if mark in self._active_marks:
                self._active_marks.remove(mark)
        if node_type:
            if node_type in {"paragraph", "heading", "codeBlock"}:
                if node_type != "codeBlock":
                    self._trim_trailing_space()
                self._at_text_block_start = False
                self._after_hard_break = False
            self.signature.append(("close", node_type))

    def handle_data(self, data: str) -> None:
        in_pre = any(entry[0] == "pre" for entry in self._stack)
        in_text_block = in_pre or any(
            entry[1] in {"paragraph", "heading"} for entry in self._stack
        )
        if not in_text_block:
            return
        if not in_pre:
            data = re.sub(r"[\t\n\f\r ]+", " ", data)
            if self._at_text_block_start or self._after_hard_break:
                data = data.lstrip(" ")
        if not data:
            return
        self._at_text_block_start = False
        self._after_hard_break = False
        self.text.append(data)
        token = ("text", data, tuple(sorted(self._active_marks)))
        if self.signature and self.signature[-1][0] == "text" and self.signature[-1][2] == token[2]:
            previous = self.signature[-1]
            self.signature[-1] = ("text", str(previous[1]) + data, previous[2])
        else:
            self.signature.append(token)

    def _trim_trailing_space(self) -> None:
        if self.text:
            self.text[-1] = self.text[-1].rstrip(" ")
            if not self.text[-1]:
                self.text.pop()
        if self.signature and self.signature[-1][0] == "text":
            previous = self.signature[-1]
            trimmed = str(previous[1]).rstrip(" ")
            if trimmed:
                self.signature[-1] = ("text", trimmed, previous[2])
            else:
                self.signature.pop()

    def close(self) -> None:
        super().close()
        self.signature.append(("close", "doc"))


def _style_value(style: str | None, name: str) -> str | None:
    if not style:
        return None
    for declaration in style.split(";"):
        key, separator, value = declaration.partition(":")
        if separator and key.strip().lower() == name:
            return value.strip()
    return None


def _document_signature(document: Document) -> list[tuple[object, ...]]:
    signature: list[tuple[object, ...]] = []

    def mark_signature(mark: Document) -> tuple[object, ...]:
        mark_type = str(mark.get("type"))
        attrs = mark.get("attrs") or {}
        if mark_type == "textStyle" and attrs.get("color"):
            return ("textStyle", "color", str(attrs["color"]).upper())
        if mark_type == "highlight" and attrs.get("color"):
            return ("highlight", "color", str(attrs["color"]).upper())
        if mark_type == "taskElement":
            return ("taskElement", str(attrs.get("languageId")), str(attrs.get("elementType")))
        if mark_type == "taskConnection":
            return ("taskConnection", str(attrs.get("languageId")), str(attrs.get("connectionType")))
        return (mark_type,)

    def visit(node: Document) -> None:
        node_type = str(node.get("type"))
        if node_type == "text":
            token = ("text", str(node.get("text", "")), tuple(sorted(mark_signature(mark) for mark in node.get("marks", []))))
            if signature and signature[-1][0] == "text" and signature[-1][2] == token[2]:
                previous = signature[-1]
                signature[-1] = ("text", str(previous[1]) + str(token[1]), previous[2])
            else:
                signature.append(token)
            return
        attrs = node.get("attrs") or {}
        canonical_attrs: list[tuple[str, object]] = []
        if node_type == "heading":
            canonical_attrs.append(("level", int(attrs.get("level", 1))))
        if node_type == "orderedList":
            canonical_attrs.append(("start", int(attrs.get("start", 1))))
        if node_type in {"heading", "paragraph"} and attrs.get("textAlign"):
            canonical_attrs.append(("textAlign", attrs["textAlign"]))
        if node_type in {"hardBreak", "horizontalRule"}:
            signature.append(("leaf", node_type, tuple(sorted(canonical_attrs))))
            return
        signature.append(("open", node_type, tuple(sorted(canonical_attrs))))
        for child in node.get("content", []):
            if isinstance(child, dict):
                visit(child)
        signature.append(("close", node_type))

    visit(document)
    return signature


def _invalid(message: str) -> ApiError:
    return ApiError(422, "INVALID_TASK_EDIT", message)


def _parse_timestamp(value: object) -> None:
    if not isinstance(value, str):
        raise _invalid("Ein Edit benötigt einen gültigen Zeitstempel.")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise _invalid("Ein Edit enthält einen ungültigen Zeitstempel.") from error


def _normalized(node: Document | None) -> Document | None:
    if node is None:
        return None
    result = deepcopy(node)
    content = result.get("content")
    if isinstance(content, list):
        normalized_children: list[Document] = []
        for child in content:
            normalized = _normalized(child) if isinstance(child, dict) else None
            if normalized is None:
                continue
            if (
                normalized_children
                and normalized.get("type") == "text"
                and normalized_children[-1].get("type") == "text"
                and normalized.get("marks", []) == normalized_children[-1].get("marks", [])
            ):
                normalized_children[-1]["text"] = str(normalized_children[-1].get("text", "")) + str(normalized.get("text", ""))
            else:
                normalized_children.append(normalized)
        if normalized_children:
            result["content"] = normalized_children
        else:
            result.pop("content", None)
    if result.get("type") == "text" and not result.get("text"):
        return None
    return result


def _project_and_validate(document: Document) -> tuple[Document, str, set[tuple[str, str, str]]]:
    edit_metadata: dict[str, tuple[str, object, object, object]] = {}
    references: set[tuple[str, str, str]] = set()
    insertion_characters = 0

    def visit(node: Document) -> Document | None:
        nonlocal insertion_characters
        node_type = node.get("type")
        if node_type not in ALLOWED_NODES:
            raise _invalid(f"Der Dokumenttyp '{node_type}' ist nicht erlaubt.")
        marks = node.get("marks", [])
        if not isinstance(marks, list):
            raise _invalid("Ungültige Mark-Struktur.")
        projected_marks: list[Document] = []
        insertion = False
        for mark in marks:
            if not isinstance(mark, dict) or mark.get("type") not in ALLOWED_MARKS:
                raise _invalid("Das Dokument enthält eine nicht erlaubte Formatierung.")
            mark_type = str(mark["type"])
            attrs = mark.get("attrs") or {}
            if not isinstance(attrs, dict):
                raise _invalid("Ungültige Edit-Attribute.")
            if mark_type in EDIT_MARKS:
                edit_id = attrs.get("editId")
                try:
                    UUID(str(edit_id))
                except (ValueError, TypeError) as error:
                    raise _invalid("Jedes Edit benötigt eine gültige UUID.") from error
                expected_type = EDIT_MARKS[mark_type]
                if attrs.get("editType") != expected_type:
                    raise _invalid("Edit-Typ und Edit-Mark stimmen nicht überein.")
                _parse_timestamp(attrs.get("createdAt"))
                if attrs.get("updatedAt") is not None:
                    _parse_timestamp(attrs.get("updatedAt"))
                if mark_type == "taskEditHighlight" and attrs.get("color") not in HIGHLIGHT_COLORS:
                    raise _invalid("Die Hervorhebungsfarbe ist nicht erlaubt.")
                if mark_type == "taskEditTextColor" and attrs.get("color") not in TEXT_COLORS:
                    raise _invalid("Die Textfarbe ist nicht erlaubt.")
                metadata = (expected_type, attrs.get("createdAt"), attrs.get("updatedAt"), attrs.get("color"))
                edit_key = str(edit_id)
                if edit_key in edit_metadata and edit_metadata[edit_key] != metadata:
                    raise _invalid("Fragmente derselben Edit-ID besitzen widersprüchliche Attribute.")
                edit_metadata[edit_key] = metadata
                insertion = insertion or mark_type == "taskEditInsertion"
                continue
            projected_marks.append(deepcopy(mark))
            if mark_type == "taskElement":
                references.add(("element", str(attrs.get("languageId")), str(attrs.get("elementType"))))
            elif mark_type == "taskConnection":
                references.add(("connection", str(attrs.get("languageId")), str(attrs.get("connectionType"))))

        if len(edit_metadata) > 1000:
            raise _invalid("Ein Modell darf höchstens 1.000 Task-Edits enthalten.")
        if node_type == "text":
            text = node.get("text")
            if not isinstance(text, str):
                raise _invalid("Ein Textknoten benötigt Text.")
            if insertion:
                insertion_characters += len(text)
                if insertion_characters > 100_000:
                    raise _invalid("Die eingefügten Texte sind zu lang.")
                return None
            result: Document = {"type": "text", "text": text}
            if projected_marks:
                result["marks"] = projected_marks
            return result

        result = {key: deepcopy(value) for key, value in node.items() if key not in {"content", "marks"}}
        content = node.get("content")
        if content is not None:
            if not isinstance(content, list):
                raise _invalid("Ungültige Dokumentstruktur.")
            result["content"] = [projected for child in content if isinstance(child, dict) and (projected := visit(child)) is not None]
        return result

    projected = _normalized(visit(document))
    if projected is None or projected.get("type") != "doc":
        raise _invalid("Das Edit-Dokument benötigt einen Dokumentknoten.")
    text_parts: list[str] = []

    def collect_text(node: Document) -> None:
        if node.get("type") == "text":
            text_parts.append(str(node.get("text", "")))
        for child in node.get("content", []):
            if isinstance(child, dict):
                collect_text(child)

    collect_text(projected)
    return projected, "".join(text_parts), references


def validate_task_edit_document(
    document: Document, original_html: str, expected_signature: str | None
) -> str:
    if len(json.dumps(document, ensure_ascii=False).encode("utf-8")) > 2_000_000:
        raise _invalid("Das Task-Edit-Dokument ist größer als 2 MB.")
    projected, projected_text, references = _project_and_validate(document)
    signature = sha256(json.dumps(projected, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
    if expected_signature is not None:
        if signature != expected_signature:
            raise _invalid("Der Originalinhalt der Aufgabe wurde verändert.")
        return signature

    parser = _OriginalHtmlParser()
    parser.feed(original_html)
    parser.close()
    if projected_text != "".join(parser.text):
        raise _invalid("Der Originaltext der Aufgabe wurde verändert.")
    if references != parser.references:
        raise _invalid("Aufgabenreferenzen dürfen nicht verändert werden.")
    if _document_signature(projected) != parser.signature:
        raise _invalid("Struktur oder Originalformatierung der Aufgabe wurde verändert.")
    return signature
