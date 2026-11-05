"""Validation for task-edit documents stored on models."""

from copy import deepcopy
from datetime import datetime
import json
from typing import Any
from uuid import UUID
from pydantic import TypeAdapter, ValidationError

from modeling_api.core.errors import ApiError
from modeling_api.db.store import Document
from modeling_api.services.task_documents import normalize_document
from modeling_api.schemas.common import JsonObject

DOCUMENT_ADAPTER = TypeAdapter(JsonObject)

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
NODE_FIELDS = {
    "doc": {"type", "content"},
    "text": {"type", "text", "marks"},
    "hardBreak": {"type", "marks"},
    "horizontalRule": {"type"},
}
NODE_ATTRIBUTES = {
    "paragraph": {"textAlign"},
    "heading": {"level", "textAlign"},
    "orderedList": {"start", "type"},
    "codeBlock": {"language"},
}
MARK_ATTRIBUTES = {
    "textStyle": {"color"},
    "highlight": {"color"},
    "taskElement": {"languageId", "elementType"},
    "taskConnection": {"languageId", "connectionType"},
}
EDIT_ATTRIBUTES = {"editId", "editType", "createdAt", "updatedAt", "color"}
TEXT_COLORS = {
    "#000000", "#424242", "#E53935", "#D81B60", "#8E24AA",
    "#1E88E5", "#00ACC1", "#43A047", "#FB8C00", "#FDD835",
}
HIGHLIGHT_COLORS = {"#FFF176", "#C8E6C9", "#BBDEFB", "#F8BBD0", "#FFE0B2", "#E1BEE7"}


def _invalid(message: str) -> ApiError:
    return ApiError(422, "INVALID_TASK_EDIT", message)


def _parse_timestamp(value: object) -> None:
    if not isinstance(value, str):
        raise _invalid("An edit requires a valid timestamp.")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise _invalid("An edit contains an invalid timestamp.") from error


def _project_and_validate(document: Document) -> Document:
    edit_metadata: dict[str, tuple[str, object, object, object]] = {}
    insertion_characters = 0

    def visit(node: Document) -> Document | None:
        nonlocal insertion_characters
        node_type = node.get("type")
        if node_type not in ALLOWED_NODES:
            raise _invalid(f"Document node type '{node_type}' is not allowed.")
        allowed_fields = NODE_FIELDS.get(
            str(node_type), {"type", "attrs", "content"}
        )
        if set(node) - allowed_fields:
            raise _invalid(f"Document node '{node_type}' contains unsupported fields.")
        node_attrs = node.get("attrs") or {}
        if not isinstance(node_attrs, dict):
            raise _invalid("Invalid node attributes.")
        allowed_node_attrs = NODE_ATTRIBUTES.get(str(node_type), set())
        if set(node_attrs) - allowed_node_attrs:
            raise _invalid(f"Document node '{node_type}' contains unsupported attributes.")
        if node_type == "heading" and node_attrs.get("level") not in {1, 2, 3}:
            raise _invalid("Task headings must use level 1, 2, or 3.")
        if node_type in {"heading", "paragraph"} and node_attrs.get("textAlign") not in {
            None,
            "left",
            "center",
            "right",
            "justify",
        }:
            raise _invalid("Text alignment is invalid.")
        if node_type == "orderedList":
            start = node_attrs.get("start", 1)
            if not isinstance(start, int) or isinstance(start, bool) or start < 1:
                raise _invalid("An ordered list requires a positive integer start value.")
            if node_attrs.get("type") not in {None, "1", "a", "A", "i", "I"}:
                raise _invalid("The ordered-list numbering type is invalid.")
        marks = node.get("marks", [])
        if not isinstance(marks, list):
            raise _invalid("Invalid mark structure.")
        projected_marks: list[Document] = []
        insertion = False
        for mark in marks:
            if not isinstance(mark, dict) or mark.get("type") not in ALLOWED_MARKS:
                raise _invalid("The document contains unsupported formatting.")
            mark_type = str(mark["type"])
            attrs = mark.get("attrs") or {}
            if not isinstance(attrs, dict):
                raise _invalid("Invalid edit attributes.")
            if set(mark) - {"type", "attrs"}:
                raise _invalid(f"Mark '{mark_type}' contains unsupported fields.")
            allowed_mark_attrs = (
                EDIT_ATTRIBUTES if mark_type in EDIT_MARKS else MARK_ATTRIBUTES.get(mark_type, set())
            )
            if set(attrs) - allowed_mark_attrs:
                raise _invalid(f"Mark '{mark_type}' contains unsupported attributes.")
            if mark_type in EDIT_MARKS:
                edit_id = attrs.get("editId")
                if not isinstance(edit_id, str):
                    raise _invalid("Every edit requires a UUID string.")
                try:
                    UUID(str(edit_id))
                except (ValueError, TypeError) as error:
                    raise _invalid("Every edit requires a valid UUID.") from error
                expected_type = EDIT_MARKS[mark_type]
                if attrs.get("editType") != expected_type:
                    raise _invalid("The edit type does not match its mark type.")
                _parse_timestamp(attrs.get("createdAt"))
                if attrs.get("updatedAt") is not None:
                    _parse_timestamp(attrs.get("updatedAt"))
                if mark_type == "taskEditHighlight" and attrs.get("color") not in HIGHLIGHT_COLORS:
                    raise _invalid("The highlight color is not allowed.")
                if mark_type == "taskEditTextColor" and attrs.get("color") not in TEXT_COLORS:
                    raise _invalid("The text color is not allowed.")
                metadata = (expected_type, attrs.get("createdAt"), attrs.get("updatedAt"), attrs.get("color"))
                edit_key = str(edit_id)
                if edit_key in edit_metadata and edit_metadata[edit_key] != metadata:
                    raise _invalid("Fragments with the same edit ID have conflicting attributes.")
                edit_metadata[edit_key] = metadata
                insertion = insertion or mark_type == "taskEditInsertion"
                continue
            projected_marks.append(deepcopy(mark))
            if mark_type == "taskElement":
                language_id = attrs.get("languageId")
                element_type = attrs.get("elementType")
                if not isinstance(language_id, str) or not isinstance(element_type, str):
                    raise _invalid("An element reference requires a language and element type.")
            elif mark_type == "taskConnection":
                language_id = attrs.get("languageId")
                connection_type = attrs.get("connectionType")
                if not isinstance(language_id, str) or not isinstance(connection_type, str):
                    raise _invalid("A connection reference requires a language and connection type.")

        if len(edit_metadata) > 1000:
            raise _invalid("A model cannot contain more than 1,000 task edits.")
        if node_type == "text":
            text = node.get("text")
            if not isinstance(text, str):
                raise _invalid("A text node requires text content.")
            if insertion:
                insertion_characters += len(text)
                if insertion_characters > 100_000:
                    raise _invalid("Inserted task text exceeds the allowed size.")
                return None
            result: Document = {"type": "text", "text": text}
            if projected_marks:
                result["marks"] = projected_marks
            return result

        result = {key: deepcopy(value) for key, value in node.items() if key not in {"content", "marks"}}
        if projected_marks:
            result["marks"] = projected_marks
        content = node.get("content")
        if content is not None:
            if not isinstance(content, list):
                raise _invalid("Invalid document structure.")
            if not all(isinstance(child, dict) for child in content):
                raise _invalid("Document content must contain nodes.")
            result["content"] = [
                projected
                for child in content
                if (projected := visit(child)) is not None
            ]
        return result

    projected = visit(document)
    if projected is None or projected.get("type") != "doc":
        raise _invalid("The task-edit document requires a root document node.")
    return normalize_document(projected)


def validate_task_edit_document(document: Document, original: Document) -> None:
    try:
        DOCUMENT_ADAPTER.validate_python(document)
    except ValidationError as error:
        raise _invalid("The task-edit document has an invalid structure or exceeds the nesting limit.") from error
    if len(json.dumps(document, ensure_ascii=False).encode("utf-8")) > 2_000_000:
        raise _invalid("The task-edit document exceeds 2 MB.")
    if _project_and_validate(document) != original:
        raise _invalid("The original task content was changed.")
