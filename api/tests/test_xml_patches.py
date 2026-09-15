from unittest import TestCase

from modeling_api.core.errors import ApiError
from modeling_api.services.xml_patches import apply_patches, validate_model_xml


BASE = """<GraphDataModel><root>
<Cell id="0"/><Cell id="1" parent="0"/>
<Cell id="a" parent="1"><Geometry x="1"/></Cell>
</root></GraphDataModel>"""


class XmlPatchTests(TestCase):
    def test_applies_ordered_cell_operations(self) -> None:
        patch = """<p:patch xmlns:p="urn:ietf:rfc:7351">
          <p:replace sel="GraphDataModel/root/Cell[@id='a']"><Cell id="a" parent="1"><Geometry x="2"/></Cell></p:replace>
          <p:add sel="GraphDataModel/root" pos="append"><Cell id="b" parent="1"/></p:add>
          <p:remove sel="GraphDataModel/root/Cell[@id='a']"/>
        </p:patch>"""

        result = apply_patches(BASE, [patch])

        self.assertIn('id="b"', result)
        self.assertNotIn('id="a"', result)

    def test_rejects_duplicate_or_empty_cell_ids(self) -> None:
        for xml in (
            '<GraphDataModel><root><Cell id=""/></root></GraphDataModel>',
            '<GraphDataModel><root><Cell id="a"/><Cell id="a"/></root></GraphDataModel>',
        ):
            with self.subTest(xml=xml), self.assertRaises(ApiError):
                validate_model_xml(xml)

    def test_rejects_patch_selectors_outside_cell_profile(self) -> None:
        patch = '<p:patch xmlns:p="urn:ietf:rfc:7351"><p:remove sel="GraphDataModel/root"/></p:patch>'
        with self.assertRaises(ApiError):
            apply_patches(BASE, [patch])
