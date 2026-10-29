"""A fixed help flow with path-local copy and immutable survey releases."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from uuid import UUID, uuid5

from modeling_api.db.client import db
from modeling_api.db.store import utcnow
from modeling_api.schemas.surveys import Definition
from modeling_api.services import surveys

PHASE_QUESTIONS = {
    "topic": ("problem_area", "other_problem"),
    "reflection": ("stuck_duration", "support_need"),
    "action": ("next_action",),
}


def blueprint():
    path = Path(__file__).parents[1] / "db" / "initial_data" / "help_questionnaires.json"
    source = json.loads(path.read_text(encoding="utf-8"))
    questions = {}
    for phase in ("reflection", "action"):
        for question in source[phase]["definition"]["elements"]:
            questions[question["name"]] = {
                "title": question["title"],
                "choices": [{"id": f"{question['name']}_{i + 1}", "text": text}
                            for i, text in enumerate(question["choices"])],
            }
    return {"topic": source["topic"]["definition"], "questions": questions}


def definition(config):
    defaults = blueprint()
    elements = deepcopy(defaults["topic"]["elements"])
    for name, fallback in defaults["questions"].items():
        edit = config.question_edits.get(name)
        content = edit.model_dump() if edit else fallback
        elements.append({
            "type": "radiogroup", "name": name, "title": content["title"], "isRequired": True,
            "choices": [c["id"] for c in content["choices"]],
            "choiceLabels": {c["id"]: c["text"] for c in content["choices"]},
        })
    return Definition.model_validate({"elements": elements}).model_dump(exclude_none=True)


def phase_definition(version, phase):
    return {"elements": [q for q in version["definition"]["elements"]
                         if q["name"] in PHASE_QUESTIONS[phase]]}


async def publish(template_id, title, revision, config, user_id=""):
    """Content-addressed releases never change answers already being collected.

    Requests resolve their release from the path content, not a mutable active
    pointer. A delayed path save therefore cannot switch a newer run backwards.
    """
    content = definition(config)
    survey_id = str(uuid5(UUID(str(template_id)), "help-questionnaire"))
    title = f"Hilfe: {title}"[:256]
    digest = sha256(json.dumps([title, content], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    version_id = str(uuid5(UUID(survey_id), digest))
    now = utcnow()
    version = {
        "_id": version_id, "surveyId": survey_id, "version": revision,
        "title": title, "definition": content, "kind": "release",
        "createdAt": now, "createdBy": user_id, "releasedAt": now, "releasedBy": user_id,
    }
    await surveys._insert_once(db.survey_versions, version)
    version = await db.survey_versions.find_one({"_id": version_id})
    fields = {
        "title": title, "definition": content, "version": version["version"],
        "latestVersionId": version_id, "latestKind": "release", "activeReleaseId": version_id,
        "activeReleaseVersion": version["version"], "updatedAt": now, "updatedBy": user_id,
        "pathRevision": revision,
    }
    await surveys._insert_once(db.surveys, {
        "_id": survey_id, **fields, "revision": 1, "schemaVersion": 2,
        "managedBy": "learning-path-help", "templateId": str(template_id), "deletedAt": None,
        "createdAt": now, "createdBy": user_id,
    })
    await db.surveys.update_one(
        {"_id": survey_id, "pathRevision": {"$lte": revision}},
        {"$set": fields},
    )
    return version
