from unittest import TestCase

from pydantic import ValidationError

from modeling_api.schemas.tasks import CreateTaskVersion
from modeling_api.services.tasks import _TaskElementMarkParser


class TaskVersionSchemaTests(TestCase):
    def test_release_requires_a_name(self) -> None:
        with self.assertRaises(ValidationError):
            CreateTaskVersion.model_validate(
                {
                    "baseVersionId": None,
                    "kind": "release",
                    "workspaceLanguages": [],
                    "data": {
                        "contentHtml": "<p>Task</p>",
                        "autonomyMode": "free",
                        "sampleSolutions": [],
                    },
                }
            )

    def test_direct_task_data_shape_is_accepted(self) -> None:
        result = CreateTaskVersion.model_validate(
            {
                "baseVersionId": None,
                "kind": "checkpoint",
                "workspaceLanguages": [],
                "data": {
                    "contentHtml": "<p>Task</p>",
                    "autonomyMode": "preventive",
                    "sampleSolutions": [],
                },
            }
        )
        self.assertEqual(result.data.autonomy_mode, "preventive")

    def test_connection_mark_is_parsed_separately_from_element_marks(self) -> None:
        parser = _TaskElementMarkParser()
        parser.feed(
            '<p><span data-task-element-language-id="language-1" data-task-element-type="entity">Entity</span> '
            '<span data-task-connection-language-id="language-1" data-task-connection-type="association">relates to</span></p>'
        )
        self.assertEqual(parser.references, [("language-1", "entity")])
        self.assertEqual(parser.connection_references, [("language-1", "association")])
