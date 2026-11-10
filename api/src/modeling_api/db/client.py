"""MongoDB connection and idempotent startup index management."""

from pymongo import ASCENDING, DESCENDING, AsyncMongoClient

from modeling_api.core.config import settings

client = AsyncMongoClient(settings.mongodb_uri, tz_aware=True)
db = client[settings.mongodb_database]


async def create_activity_indexes() -> None:
    """Indexes shared by startup and the activity migration."""
    await db.model_activity_sessions.create_index(
        [("modelId", ASCENDING), ("createdAt", DESCENDING), ("_id", DESCENDING)]
    )
    await db.model_activity_interactions.create_index(
        [("sessionId", ASCENDING), ("createdAt", ASCENDING), ("_id", DESCENDING)]
    )


async def create_submission_indexes() -> None:
    """Indexes shared by startup and the submissions migration."""
    # New human-feedback storage is separate from legacy feedback and model data.
    await db.submission_assignments.create_index([("archived", ASCENDING), ("createdAt", DESCENDING)])
    await db.submission_runs.create_index([("assignmentId", ASCENDING), ("createdAt", DESCENDING)])
    await db.submission_participants.create_index([("runId", ASCENDING), ("userId", ASCENDING)], unique=True)
    await db.submission_participants.create_index([("userId", ASCENDING), ("runId", ASCENDING)])
    await db.submissions.create_index([("runId", ASCENDING), ("ownerId", ASCENDING), ("createdAt", DESCENDING)])
    await db.submission_reviews.create_index([("submissionId", ASCENDING), ("kind", ASCENDING)])
    await db.submission_reviews.create_index([("runId", ASCENDING), ("status", ASCENDING)])
    await db.submission_publications.create_index([("reviewId", ASCENDING), ("number", DESCENDING)])
    await db.submission_resolutions.create_index([("submissionId", ASCENDING), ("userId", ASCENDING)])


async def create_indexes() -> None:
    """Create indexes required by API query patterns."""
    await create_activity_indexes()
    await create_submission_indexes()
    await db.surveys.create_index([("deletedAt", ASCENDING), ("createdAt", DESCENDING)])
    await db.survey_versions.create_index(
        [("surveyId", ASCENDING), ("version", DESCENDING)], unique=True
    )
    await db.survey_sessions.create_index(
        [("releaseId", ASCENDING), ("status", ASCENDING), ("completedAt", DESCENDING)]
    )
    for collection in ("languages", "task", "models"):
        await db[collection].create_index(
            [("ownerId", ASCENDING), ("createdAt", DESCENDING), ("_id", DESCENDING)]
        )

    for collection, parent_field in (
        ("language_versions", "languageId"),
        ("task_version", "taskId"),
        ("model_versions", "modelId"),
    ):
        await db[collection].create_index(
            [(parent_field, ASCENDING), ("versionNumber", DESCENDING)], unique=True
        )

    await db.task_version.create_index(
        [("taskId", ASCENDING), ("kind", ASCENDING), ("createdAt", DESCENDING)]
    )
    await db.task.create_index(
        [
            ("archivedAt", ASCENDING),
            ("ownerId", ASCENDING),
            ("visibility", ASCENDING),
            ("name", ASCENDING),
        ]
    )
    await db.models.create_index(
        [
            ("ownerId", ASCENDING),
            ("taskVersion.taskId", ASCENDING),
            ("updatedAt", DESCENDING),
        ]
    )
    await db.task_edit_versions.create_index([("modelId", ASCENDING), ("patches.id", ASCENDING)], unique=True)
    await db.task_edit_versions.create_index(
        [("modelId", ASCENDING), ("baseReleaseId", ASCENDING), ("revision", ASCENDING)]
    )

    await db.feedback.create_index(
        [("source", ASCENDING), ("externalFeedbackId", ASCENDING)], unique=True
    )
    await db.feedback.create_index(
        [
            ("modelId", ASCENDING),
            ("modelVersionId", ASCENDING),
            ("createdAt", DESCENDING),
        ]
    )
    await db.model_versions.create_index(
        [("modelId", ASCENDING), ("baseReleaseId", ASCENDING), ("createdAt", ASCENDING)]
    )
    await db.evaluations.create_index(
        [("ownerId", ASCENDING), ("taskId", ASCENDING), ("createdAt", DESCENDING)]
    )
    await db.evaluations.create_index(
        [("dagName", ASCENDING), ("dagRunId", ASCENDING)], unique=True
    )

    await db.learning_path_template_steps.create_index("templateId")
    await db.learning_path_help_requests.create_index(
        [("runId", ASCENDING), ("stepId", ASCENDING), ("createdAt", DESCENDING)]
    )
    await db.learning_path_pulse_events.create_index(
        [("runId", ASCENDING), ("stepId", ASCENDING), ("at", DESCENDING)]
    )
    await db.learning_path_pulse_events.create_index(
        [("runId", ASCENDING), ("stepId", ASCENDING), ("offerSeq", ASCENDING)],
        unique=True, partialFilterExpression={"event": "offered"},
    )
    await db.learning_path_pulse_events.create_index(
        [("offerId", ASCENDING)], unique=True,
        partialFilterExpression={"reaction": True},
    )
    await db.learning_path_pulse_events.create_index(
        [("runId", ASCENDING), ("sessionKey", ASCENDING), ("event", ASCENDING)]
    )
    await db.learning_path_run_steps.create_index("modelId")
    await db.learning_path_run_steps.create_index(
        [("runId", ASCENDING), ("stepId", ASCENDING)], unique=True
    )
    await db.learning_path_runs.create_index(
        [("learnerId", ASCENDING), ("templateId", ASCENDING)], unique=True
    )
