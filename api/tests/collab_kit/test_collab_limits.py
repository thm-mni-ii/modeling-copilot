"""The limits of the backend and of the Copilot must be the same."""

import json
from pathlib import Path

import pytest

from modeling_api.services.collab_kit.collab_settings import LIMITS

# The file the web uses; the tests run in the repository, the API image has no web folder.
WEB_LIMITS = Path(__file__).resolve().parents[3] / "web/src/collab/settings/backendLimits.json"


def test_limits_match_the_web():
    if not WEB_LIMITS.exists():
        pytest.skip("web/src/collab/settings/backendLimits.json not found")
    assert json.loads(WEB_LIMITS.read_text()) == LIMITS
