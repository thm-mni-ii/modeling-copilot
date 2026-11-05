"""Stable identities for the built-in help-request questionnaires."""

from uuid import UUID, uuid5

HELP_NAMESPACE = UUID("5eff2fa9-17c4-4bd5-b44e-fc98bc05f325")
HELP_SURVEY_IDS = {
    phase: str(uuid5(HELP_NAMESPACE, f"help:{phase}"))
    for phase in ("topic", "reflection", "action")
}
