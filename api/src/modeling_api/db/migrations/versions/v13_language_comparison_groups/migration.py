"""Add comparison groups to language versions without evaluation settings."""

from modeling_api.db.client import db
from modeling_api.db.migrations import require_completed, run_migration

MIGRATION_ID = "13_language_comparison_groups"
PREREQUISITE = "12_laboratory_management"

GROUPS = (
    ("serm-entity", "Entity", ("serm-entity", "serm-er", "serm-relationship")),
    ("serm-attribute", "Attribute", ("serm-attribute", "serm-key-attribute")),
    ("serm-generalization", "Generalization", ("serm-generalization", "serm-generalization-disjoint")),
    ("erm-entity", "Entity", ("erm-entity", "erm-weak-entity")),
    ("erm-relationship", "Relationship", ("erm-relationship", "erm-weak-relationship")),
    ("erm-attribute", "Attribute", ("erm-attribute", "erm-key-attribute", "erm-multivalued-attribute")),
    ("uml-class", "Class", ("uml-class", "uml-abstract-class")),
)

CONNECTION_GROUPS = (
    ("serm-connection", "Relationship", ("serm-0-1", "serm-0-n", "serm-1-1", "serm-1-n")),
    ("uml-association", "Association", ("uml-association", "uml-directed-association", "uml-aggregation", "uml-composition")),
)


def evaluation_config(data):
    element_types = set()

    def collect(elements):
        if not isinstance(elements, list):
            raise ValueError("Language element declarations must be a list.")
        for element in elements:
            if not isinstance(element, dict) or not isinstance(element.get("type"), str):
                raise ValueError("Language element declarations must have a type identifier.")
            element_types.add(element["type"])
            collect(element.get("children", []))

    collect(data.get("elements", []))
    connections = data.get("connections", [])
    if not isinstance(connections, list) or any(
        not isinstance(connection, dict) or not isinstance(connection.get("type"), str)
        for connection in connections
    ):
        raise ValueError("Language connection declarations must be a list with type identifiers.")
    connection_types = {connection["type"] for connection in connections}
    groups = []
    for group_id, name, candidates in GROUPS:
        members = [element_type for element_type in candidates if element_type in element_types]
        if len(members) >= 2:
            groups.append({"id": group_id, "name": name, "elementTypes": members})
    for group_id, name, candidates in CONNECTION_GROUPS:
        members = [connection_type for connection_type in candidates if connection_type in connection_types]
        if len(members) >= 2:
            groups.append({"id": group_id, "name": name, "connectionTypes": members})
    return {"comparisonGroups": groups}


async def migrate(*, apply=False):
    await require_completed(PREREQUISITE)
    previous = await db.schema_migrations.find_one({"_id": MIGRATION_ID})
    if previous and previous.get("status") == "completed":
        print(f"{MIGRATION_ID} already completed; skipping.")
        return 0
    if not apply:
        return await migrate_versions(apply=False)
    return await run_migration(MIGRATION_ID, lambda: migrate_versions(apply=True))


async def migrate_versions(*, apply):
    changed = 0
    async for version in db.language_versions.find({}):
        data = version["data"]
        if "evaluation" in data:
            continue
        try:
            evaluation = evaluation_config(data)
        except ValueError as error:
            raise RuntimeError(f'Invalid language version {version["_id"]}: {error}') from error
        print(f'{"Configure" if apply else "Would configure"}: language version {version["_id"]}')
        if apply:
            result = await db.language_versions.update_one(
                {"_id": version["_id"], "data": data},
                {"$set": {"data.evaluation": evaluation}},
            )
            if not result.matched_count:
                raise RuntimeError(
                    f'Language version {version["_id"]} changed during migration; stop language writes before retrying.'
                )
        changed += 1
    return changed
