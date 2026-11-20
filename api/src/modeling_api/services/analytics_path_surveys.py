"""Staff analytics over the surveys of one learning path, limited to the answers of that path's participants.

Sessions are found through the runs, never through the survey: linked from run steps (task before/after
questionnaires and survey steps, see SESSION_LINKS), the session ids of the pulse offers of the runs, and
the combined session of each help request. A survey can be used several times in a path, so answers are
aggregated per survey and release; `usages` only says where the survey occurs in the template.
Only aggregated values leave this module; test sessions are ignored.
"""

from collections import defaultdict
from datetime import UTC, datetime, timedelta

from modeling_api.db.client import db
from modeling_api.services import analytics_paths
from modeling_api.services.analytics_surveys import RECENT_DAYS, SESSION_LINKS, session_summary, survey_questions
from modeling_api.services.learning_path_progress import require_access
from modeling_api.services.learning_path_store import template_document
from modeling_api.services.pulse_surveys import session_id as pulse_session_id


def declared_usages(template):
    """survey id -> where the template uses it (task before/after, survey step, pulse pool), in template order."""
    usages = defaultdict(list)

    def add(survey_id, text):
        if survey_id and text not in usages[str(survey_id)]:
            usages[str(survey_id)].append(text)

    for step in template["steps"]:
        if step.get("archivedAt"):
            continue
        if step["kind"] == "task":
            add(step["task"].get("beforeSurveyId"), f"Before task: {step['title']}")
            add(step["task"].get("afterSurveyId"), f"After task: {step['title']}")
        else:
            add(step["survey"]["surveyId"], f"Survey step: {step['title']}")
    for survey_id in (template.get("pulseSurveys") or {}).get("surveyIds", []):
        add(survey_id, "Pulse pool")
    return usages


async def linked_session_ids(run_ids):
    """Ids of all sessions of the runs, plus the survey ids of their pulse offers."""
    ids, offered = set(), set()
    async for state in db.learning_path_run_steps.find({"runId": {"$in": run_ids}}, dict.fromkeys(SESSION_LINKS, 1)):
        ids.update(state[field] for field in SESSION_LINKS if state.get(field))
    async for offer in db.learning_path_pulse_events.find(
        {"runId": {"$in": run_ids}, "event": "offered"}, {"runId": 1, "stepId": 1, "surveyId": 1}
    ):
        ids.add(pulse_session_id(offer))
        offered.add(offer["surveyId"])
    async for request in db.learning_path_help_requests.find(
        {"runId": {"$in": run_ids}, "surveySessionId": {"$ne": None}}, {"surveySessionId": 1}
    ):
        ids.add(request["surveySessionId"])
    return ids, offered


def submitted_between(sessions, start, end):
    return [
        session for session in sessions
        if session["status"] == "submitted" and session.get("completedAt") and start <= session["completedAt"] < end
    ]


def release_entry(release, active, sessions, now):
    recent = submitted_between(sessions, now - timedelta(days=RECENT_DAYS), now + timedelta(seconds=1))
    questions = survey_questions(release["definition"], sessions)
    last_week = {question["name"]: question for question in survey_questions(release["definition"], recent)}
    return {
        "id": release["_id"], "version": release["version"], "releasedAt": release.get("releasedAt"), "active": active,
        "submitted": sum(session["status"] == "submitted" for session in sessions),
        "ratings": [{
            "name": question["name"], "title": question["title"], "responses": question["responses"],
            "meanOverall": question["mean"], "meanLastWeek": last_week[question["name"]]["mean"],
            "responsesLastWeek": last_week[question["name"]]["responses"],
        } for question in questions if question["kind"] == "rating"],
        "questions": questions,
    }


async def path_surveys(template_id, include_staff, user):
    require_access(user)
    template = await template_document(template_id)
    run_ids = await analytics_paths.run_ids(template["_id"], include_staff)
    usages = declared_usages(template)
    ids, offered = await linked_session_ids(run_ids)
    for survey_id in offered:
        if "Pulse pool" not in usages[survey_id]:
            usages[survey_id].append("Pulse pool")
    sessions = await db.survey_sessions.find(
        {"_id": {"$in": list(ids)}, "isTest": {"$ne": True}}, {"status": 1, "answers": 1, "completedAt": 1, "releaseId": 1}
    ).to_list(None)
    releases = {
        release["_id"]: release async for release in db.survey_versions.find(
            {"_id": {"$in": list({session["releaseId"] for session in sessions})}}, {"surveyId": 1, "version": 1, "releasedAt": 1, "definition": 1}
        )
    }
    answered = defaultdict(lambda: defaultdict(list))  # survey id -> release id -> sessions
    for session in sessions:
        if session["releaseId"] in releases:
            answered[releases[session["releaseId"]]["surveyId"]][session["releaseId"]].append(session)
    # The help questionnaire is generated per path and not referenced by template steps.
    help_survey = await db.surveys.find_one({"managedBy": "learning-path-help", "templateId": template["_id"]}, {"_id": 1})
    if help_survey and (template.get("helpRequests", {}).get("enabled") or help_survey["_id"] in answered):
        usages[help_survey["_id"]].append("Help questionnaire")
    survey_ids = list(dict.fromkeys([*usages, *answered]))
    documents = {doc["_id"]: doc async for doc in db.surveys.find({"_id": {"$in": survey_ids}}, {"title": 1, "activeReleaseId": 1})}
    now = datetime.now(UTC)
    result = []
    for survey_id in survey_ids:
        by_release = answered.get(survey_id, {})
        every = [session for group in by_release.values() for session in group]
        document = documents.get(survey_id, {})
        result.append({
            "id": survey_id, "title": document.get("title", survey_id), "usages": usages.get(survey_id, []),
            **session_summary(every),
            "submittedPreviousWeek": len(submitted_between(every, now - timedelta(days=2 * RECENT_DAYS), now - timedelta(days=RECENT_DAYS))),
            "releases": [
                release_entry(releases[release_id], release_id == document.get("activeReleaseId"), group, now)
                for release_id, group in sorted(by_release.items(), key=lambda item: releases[item[0]]["version"], reverse=True)
            ],
        })
    return {"surveys": result}
