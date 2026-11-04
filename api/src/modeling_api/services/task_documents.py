"""Canonical task documents shared by the editor and annotation validation."""

import re
from copy import deepcopy

from lxml import html

from modeling_api.db.store import Document

BLOCKS = {
    "p": "paragraph", "h1": "heading", "h2": "heading", "h3": "heading",
    "ul": "bulletList", "ol": "orderedList", "li": "listItem",
    "blockquote": "blockquote", "pre": "codeBlock", "hr": "horizontalRule",
}
MARKS = {"strong": "bold", "b": "bold", "em": "italic", "i": "italic",
         "u": "underline", "s": "strike", "strike": "strike", "del": "strike", "code": "code"}


def normalize_document(node: Document) -> Document:
    """Ignore editor defaults and text splitting, but preserve content and formatting."""
    result = {key: deepcopy(value) for key, value in node.items()
              if key not in {"attrs", "marks", "content"}}
    attrs = {key: value for key, value in (node.get("attrs") or {}).items() if value is not None}
    if attrs:
        result["attrs"] = attrs
    marks = [normalize_document(mark) for mark in node.get("marks", [])]
    if marks:
        result["marks"] = sorted(marks, key=lambda mark: mark["type"])
    content = []
    for child in node.get("content", []):
        child = normalize_document(child)
        if child.get("type") == "text" and not child.get("text"):
            continue
        if content and child["type"] == "text" and content[-1]["type"] == "text" and child.get("marks") == content[-1].get("marks"):
            content[-1]["text"] += child["text"]
        else:
            content.append(child)
    if content:
        result["content"] = content
    return result


def task_document(source: str) -> Document:
    """Import HTML once on the server; consumers use this JSON without reparsing HTML."""
    root = html.fragment_fromstring(source or "<p></p>", create_parent="div")

    def style(element):
        return dict(part.strip().lower().split(":", 1) for part in element.get("style", "").split(";") if ":" in part)

    def marks_for(element, inherited, pre):
        marks = deepcopy(inherited)
        tag = element.tag.lower()
        if tag in MARKS and not (pre and tag == "code"):
            marks.append({"type": MARKS[tag]})
        styles = {key.strip(): value.strip() for key, value in style(element).items()}
        color = styles.get("color")
        if color and color != "inherit":
            marks.append({"type": "textStyle", "attrs": {"color": color.upper()}})
        highlight = element.get("data-color") if tag == "mark" else styles.get("background-color")
        if highlight:
            marks.append({"type": "highlight", "attrs": {"color": highlight.upper()}})
        for kind, field in (("element", "elementType"), ("connection", "connectionType")):
            language = element.get(f"data-task-{kind}-language-id")
            reference = element.get(f"data-task-{kind}-type")
            if language and reference:
                marks.append({"type": "taskElement" if kind == "element" else "taskConnection",
                              "attrs": {"languageId": language, field: reference}})
        # Nested HTML marks of the same type have the innermost attributes.
        return list({mark["type"]: mark for mark in marks}.values())

    def children(element, pre=False, inherited=None):
        inherited = inherited or []
        result = []
        inline = []

        def text(value, marks):
            if not value:
                return
            if not pre:
                value = re.sub(r"[\t\n\f\r ]+", " ", value)
                if not inline or inline[-1].get("type") == "hardBreak" or inline[-1].get("text", "").endswith(" "):
                    value = value.lstrip(" ")
            if value:
                inline.append({"type": "text", "text": value, **({"marks": marks} if marks else {})})

        def flush():
            if not pre and inline and inline[-1]["type"] == "text":
                inline[-1]["text"] = inline[-1]["text"].rstrip(" ")
            if inline:
                result.append({"type": "paragraph", "content": list(inline)})
                inline.clear()

        def visit(child, inherited):
            if not isinstance(child.tag, str):
                return
            tag = child.tag.lower()
            if tag in BLOCKS:
                flush()
                kind = BLOCKS[tag]
                node = {"type": kind}
                attrs = {}
                if kind == "heading":
                    attrs["level"] = int(tag[1])
                if kind in {"heading", "paragraph"}:
                    align = style(child).get("text-align", "").strip()
                    if align:
                        attrs["textAlign"] = align
                if kind == "orderedList":
                    attrs["start"] = int(child.get("start", "1"))
                    if child.get("type"):
                        attrs["type"] = child.get("type")
                if attrs:
                    node["attrs"] = attrs
                nested = children(child, kind == "codeBlock", marks_for(child, inherited, kind == "codeBlock"))
                if kind in {"paragraph", "heading", "codeBlock"}:
                    node["content"] = [item for paragraph in nested for item in paragraph.get("content", [])]
                elif kind != "horizontalRule":
                    node["content"] = nested
                    if kind == "listItem" and (not nested or nested[0]["type"] != "paragraph"):
                        node["content"].insert(0, {"type": "paragraph"})
                result.append(node)
            elif tag == "br":
                inline.append({"type": "hardBreak"})
            elif tag not in {"script", "style"}:
                marks = marks_for(child, inherited, pre)
                text(child.text, marks)
                for descendant in child:
                    visit(descendant, marks)
                    text(descendant.tail, marks)

        text(element.text, inherited)
        for child in element:
            visit(child, inherited)
            text(child.tail, inherited)
        flush()
        return result

    return normalize_document({"type": "doc", "content": children(root) or [{"type": "paragraph"}]})
