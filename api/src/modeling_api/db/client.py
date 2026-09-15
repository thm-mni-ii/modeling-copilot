"""MongoDB-Verbindung und Index-Anlage. Läuft einmalig beim API-Start."""

from pymongo import ASCENDING, DESCENDING, AsyncMongoClient

from modeling_api.core.config import settings

client = AsyncMongoClient(settings.mongodb_uri, tz_aware=True)
db = client[settings.mongodb_database]


async def create_indexes() -> None:
    """Legt die Indizes an (idempotent, also bei jedem Start gefahrlos wiederholbar).

    Die Unique-Indizes sind gleichzeitig die Absicherung gegen doppelte
    Schreibvorgänge, z. B. zwei gleichzeitig angehängte Versionen.
    """
    # In-place migration from the former external task-statement vocabulary.
    await db.task_statement_versions.update_many(
        {"taskStatementId": {"$exists": True}},
        {"$rename": {"taskStatementId": "taskId"}},
    )
    await db.model_versions.update_many(
        {"taskVersion.taskStatementId": {"$exists": True}},
        {"$rename": {"taskVersion.taskStatementId": "taskVersion.taskId"}},
    )
    await db.models.update_many(
        {"taskVersion.taskStatementId": {"$exists": True}},
        {"$rename": {"taskVersion.taskStatementId": "taskVersion.taskId"}},
    )

    index_names = await db.task_statements.index_information()
    if "source_1_externalTaskId_1" in index_names:
        await db.task_statements.drop_index("source_1_externalTaskId_1")
    version_index_names = await db.task_statement_versions.index_information()
    if "taskStatementId_1_versionNumber_-1" in version_index_names:
        await db.task_statement_versions.drop_index("taskStatementId_1_versionNumber_-1")
    if "taskStatementId_1_externalVersionId_1" in version_index_names:
        await db.task_statement_versions.drop_index("taskStatementId_1_externalVersionId_1")

    for collection in ("languages", "task_statements", "models"):
        await db[collection].create_index(
            [("ownerId", ASCENDING), ("createdAt", DESCENDING), ("_id", DESCENDING)]
        )

    for collection, parent_field in (
        ("language_versions", "languageId"),
        ("task_statement_versions", "taskId"),
        ("model_versions", "modelId"),
    ):
        await db[collection].create_index(
            [(parent_field, ASCENDING), ("versionNumber", DESCENDING)], unique=True
        )

    await db.task_statement_versions.create_index(
        [("taskId", ASCENDING), ("kind", ASCENDING), ("createdAt", DESCENDING)]
    )
    await db.models.create_index(
        [("ownerId", ASCENDING), ("taskVersion.taskId", ASCENDING), ("updatedAt", DESCENDING)]
    )

    await db.feedback.create_index(
        [("source", ASCENDING), ("externalFeedbackId", ASCENDING)], unique=True
    )
    await db.feedback.create_index(
        [("modelId", ASCENDING), ("modelVersionId", ASCENDING), ("createdAt", DESCENDING)]
    )
    await db.model_versions.create_index(
        [("modelId", ASCENDING), ("baseReleaseId", ASCENDING), ("createdAt", ASCENDING)]
    )
