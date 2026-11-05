"""Resolve and validate the questionnaires used by a help flow."""

from modeling_api.core.errors import ApiError
from modeling_api.db.help_questionnaires import HELP_SURVEY_IDS
from modeling_api.schemas.learning_paths import HelpRequestConfig
from modeling_api.services import surveys


def survey_ids(config: HelpRequestConfig):
    return {
        phase: str(getattr(config, f"{phase}_survey_id") or default)
        for phase, default in HELP_SURVEY_IDS.items()
    }


def validate_phase(phase, version, config: HelpRequestConfig):
    if phase == "reflection" or (phase == "topic" and not config.marking_enabled):
        return
    name = config.topic_question if phase == "topic" else config.action_question
    question = next((q for q in version["definition"]["elements"] if q["name"] == name), None)
    label = "Problembezug" if phase == "topic" else "Nächste Hilfequelle"
    if not question or question["type"] != "radiogroup" or not question.get("isRequired") or question.get("visibleIf"):
        raise ApiError(422, "INVALID_HELP_CONFIGURATION", f"{label}: Wähle eine verpflichtende, immer sichtbare Einfachauswahl-Frage aus dem veröffentlichten Fragebogen.")
    if phase == "topic" and config.marking_answer not in question["choices"]:
        raise ApiError(422, "INVALID_HELP_CONFIGURATION", "Problembezug: Die Antwort für den Markierungsmodus ist im veröffentlichten Fragebogen nicht vorhanden.")


async def validate_config(config: HelpRequestConfig, user):
    ids = survey_ids(config)
    for phase, survey_id in ids.items():
        version = await surveys.render(survey_id, user, "use")
        validate_phase(phase, version, config)
    return ids
