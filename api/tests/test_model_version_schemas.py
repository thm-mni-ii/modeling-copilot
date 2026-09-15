from datetime import UTC, datetime
from unittest import TestCase

from pydantic import ValidationError

from modeling_api.schemas.models import CreateModelVersion


class ModelVersionSchemaTests(TestCase):
    def test_release_rejects_local_patches(self) -> None:
        with self.assertRaises(ValidationError):
            CreateModelVersion.model_validate(
                {
                    "baseVersionId": None,
                    "kind": "release",
                    "releaseName": "v1",
                    "data": {"xml": "<GraphDataModel><root/></GraphDataModel>"},
                    "patches": [
                        {
                            "createdAt": datetime.now(UTC).isoformat(),
                            "xml": '<p:patch xmlns:p="urn:ietf:rfc:7351"/>',
                        }
                    ],
                }
            )

    def test_checkpoint_rejects_full_xml_snapshot(self) -> None:
        with self.assertRaises(ValidationError):
            CreateModelVersion.model_validate(
                {
                    "baseVersionId": None,
                    "kind": "checkpoint",
                    "data": {"xml": "<GraphDataModel><root/></GraphDataModel>"},
                }
            )
