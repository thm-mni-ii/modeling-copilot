from unittest import TestCase

from modeling_api.core.errors import ApiError
from modeling_api.services.task_edits import validate_task_edit_document


class TaskEditValidationTests(TestCase):
    def setUp(self) -> None:
        self.document = {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": "Hello",
                            "marks": [
                                {
                                    "type": "taskEditHighlight",
                                    "attrs": {
                                        "editId": "6cfce068-a0bb-4e80-92c8-25b5dcff72bb",
                                        "editType": "highlight",
                                        "createdAt": "2026-09-16T12:00:00+00:00",
                                        "updatedAt": None,
                                        "color": "#FFF176",
                                    },
                                }
                            ],
                        },
                        {
                            "type": "text",
                            "text": " note",
                            "marks": [
                                {
                                    "type": "taskEditInsertion",
                                    "attrs": {
                                        "editId": "00b41b27-79f1-42ef-9705-c3e18fe65e7f",
                                        "editType": "insertion",
                                        "createdAt": "2026-09-16T12:01:00+00:00",
                                        "updatedAt": None,
                                        "color": None,
                                    },
                                }
                            ],
                        },
                    ],
                }
            ],
        }

    def test_formats_and_insertions_preserve_original(self) -> None:
        signature = validate_task_edit_document(self.document, "<p>Hello</p>", None)
        self.assertEqual(64, len(signature))
        self.assertEqual(signature, validate_task_edit_document(self.document, "<p>Hello</p>", signature))

    def test_rejects_changed_original_text(self) -> None:
        self.document["content"][0]["content"][0]["text"] = "Changed"
        with self.assertRaises(ApiError):
            validate_task_edit_document(self.document, "<p>Hello</p>", None)

    def test_rejects_edit_attribute_changes_for_same_id(self) -> None:
        duplicate = dict(self.document["content"][0]["content"][0])
        duplicate["text"] = "Hello"
        duplicate["marks"] = [dict(self.document["content"][0]["content"][0]["marks"][0])]
        duplicate["marks"][0]["attrs"] = dict(duplicate["marks"][0]["attrs"], color="#C8E6C9")
        self.document["content"][0]["content"].append(duplicate)
        with self.assertRaises(ApiError):
            validate_task_edit_document(self.document, "<p>HelloHello</p>", None)

    def test_rejects_changed_original_formatting(self) -> None:
        self.document["content"][0]["content"][0]["marks"].append({"type": "bold"})
        with self.assertRaises(ApiError):
            validate_task_edit_document(self.document, "<p>Hello</p>", None)

    def test_accepts_preserved_task_reference_below_an_edit(self) -> None:
        self.document["content"][0]["content"][0]["marks"].append(
            {"type": "taskElement", "attrs": {"languageId": "language-1", "elementType": "Class"}}
        )
        signature = validate_task_edit_document(
            self.document,
            '<p><span data-task-element-language-id="language-1" data-task-element-type="Class">Hello</span></p>',
            None,
        )
        self.assertEqual(64, len(signature))

    def test_ignores_html_layout_whitespace_around_blocks_and_hard_breaks(self) -> None:
        document = {
            "type": "doc",
            "content": [
                {
                    "type": "heading",
                    "attrs": {"level": 2, "textAlign": None},
                    "content": [{"type": "text", "text": "Heading"}],
                },
                {
                    "type": "paragraph",
                    "attrs": {"textAlign": None},
                    "content": [
                        {"type": "text", "text": "A "},
                        {
                            "type": "text",
                            "text": "Customer",
                            "marks": [
                                {"type": "textStyle", "attrs": {"color": "rgb(30, 136, 229)"}},
                                {"type": "bold"},
                            ],
                        },
                        {"type": "text", "text": "."},
                        {"type": "hardBreak"},
                        {"type": "text", "text": "Each order"},
                    ],
                },
            ],
        }

        signature = validate_task_edit_document(
            document,
            '<h2>Heading</h2>\n<p>A <span style="color: rgb(30, 136, 229);">'
            "<strong>Customer</strong></span>.<br>\nEach order</p>",
            None,
        )

        self.assertEqual(64, len(signature))
