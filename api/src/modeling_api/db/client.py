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
    for collection in ("languages", "task_statements", "models"):
        await db[collection].create_index(
            [("ownerId", ASCENDING), ("createdAt", DESCENDING), ("_id", DESCENDING)]
        )

    await db.task_statements.create_index(
        [("source", ASCENDING), ("externalTaskId", ASCENDING)], unique=True
    )

    for collection, parent_field in (
        ("language_versions", "languageId"),
        ("task_statement_versions", "taskStatementId"),
        ("model_versions", "modelId"),
    ):
        await db[collection].create_index(
            [(parent_field, ASCENDING), ("versionNumber", DESCENDING)], unique=True
        )

    await db.task_statement_versions.create_index(
        [("taskStatementId", ASCENDING), ("externalVersionId", ASCENDING)], unique=True
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
