"""Recognition uses existing comparison groups without extra category metadata."""
from pathlib import Path
import json

import pytest
from pydantic import ValidationError

from modeling_api.schemas.languages import CreateLanguageVersion


def definition():
    return {"elements": [{"type": "box", "children": [{"type": "property"}]}, {"type": "unclassified"}],
            "connections": [{"type": "edge"}], "evaluation": {"comparisonGroups": [{"id": "g", "name": "Group", "elementTypes": ["box", "property"]}]}}


def test_existing_comparison_groups_need_no_category_metadata():
    CreateLanguageVersion.model_validate({"baseVersionId": None, "data": definition()})


@pytest.mark.parametrize("members", [["unknown", "box"], ["box"], ["box", "box"], ["edge", "box"]])
def test_invalid_comparison_group_members_are_rejected(members):
    data = definition()
    data["evaluation"]["comparisonGroups"][0]["elementTypes"] = members
    with pytest.raises(ValidationError):
        CreateLanguageVersion.model_validate({"baseVersionId": None, "data": data})


def test_historical_language_definitions_remain_readable_without_new_categories():
    versions = Path(__file__).resolve().parents[1] / "src/modeling_api/db/migrations/versions"
    paths = [versions / "v00_initial_data" / name for name in ("erm.json", "serm.json", "uml_class_diagram.json")]
    paths += [versions / "v01_connection_rule_aliases" / name for name in ("erm_v2.json", "serm_v2.json")]
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        CreateLanguageVersion.model_validate({"baseVersionId": None, "data": data})
        assert "evaluation" not in data


def test_evaluation_snapshot_freezes_existing_groups_without_injecting_categories():
    import asyncio
    from unittest.mock import AsyncMock, patch
    from modeling_api.services import evaluations

    pin = {"languageId": "00000000-0000-0000-0000-000000000001", "versionId": "00000000-0000-0000-0000-000000000002"}
    snapshot = {"modelId": "model", "versionId": "version", "workspaceLanguages": [pin], "data": {}}
    override = {"graphMatching": {"minimumSimilarity": {"test": 0.8}}}
    with patch.object(evaluations.languages, "get_version", new=AsyncMock(return_value={"data": definition()})) as read:
        bundle, _ = asyncio.run(evaluations._evaluation_input("evaluation", {}, snapshot, [snapshot], comparison_config=override))
    read.assert_awaited_once()
    assert "elementCategories" not in bundle["comparisonConfig"]["graphMatching"]
    assert bundle["languages"][0]["data"]["evaluation"]["comparisonGroups"] == definition()["evaluation"]["comparisonGroups"]
    assert bundle["languages"][0]["versionId"] == pin["versionId"]
    assert bundle["comparisonConfig"]["graphMatching"]["minimumSimilarity"] == {"test": 0.8}
    assert "elementCategories" not in override["graphMatching"]
