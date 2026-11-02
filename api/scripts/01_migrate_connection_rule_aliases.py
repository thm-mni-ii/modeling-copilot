"""Publish canonical language releases; historical releases and models stay pinned.

Run with PYTHONPATH=api/src. The default is a read-only preview:
  python api/scripts/01_migrate_connection_rule_aliases.py
  python api/scripts/01_migrate_connection_rule_aliases.py --apply
Use --language-id UUID to limit the read-only preview to one language.
Run 00_initial_data.py --apply first to initialize or adopt the baseline.
This migration publishes ERM/SERM 2.0 before normalizing other current releases.
MongoDB configuration is read from the application's normal environment.
"""

import argparse
import asyncio
from uuid import UUID, uuid5

from modeling_api.core.auth import User
from modeling_api.db.client import client, db
from modeling_api.db.initial_data import (
    ERM_ID, ERM_VERSION_ID, SERM_ID, SERM_VERSION_ID, SYSTEM_OWNER_ID,
    _load_initial_data,
)
from modeling_api.db.migrations import BASELINE_ID, LANGUAGE_UPGRADE_ID, require_completed, run_migration
from modeling_api.db.store import utcnow
from modeling_api.schemas.languages import CreateLanguageVersion
from modeling_api.services.languages import create_version, normalize_definition

MIGRATION_ID = LANGUAGE_UPGRADE_ID
LANGUAGE_RELEASES = {
    ERM_ID: (ERM_VERSION_ID, "erm_v2.json"),
    SERM_ID: (SERM_VERSION_ID, "serm_v2.json"),
}


async def migrate(*, apply=False, language_id=None):
    if apply and language_id is not None:
        raise RuntimeError("--language-id is only supported for the read-only preview; apply must cover the whole database.")
    await require_completed(BASELINE_ID)
    previous = await db.schema_migrations.find_one({"_id": MIGRATION_ID})
    if previous and previous.get("status") == "completed":
        print(f"{MIGRATION_ID} already completed; skipping.")
        return 0
    query = {"archivedAt": None}
    if language_id is not None:
        query["_id"] = str(language_id)
    if not apply:
        return await migrate_languages(query, apply=False)

    return await run_migration(MIGRATION_ID, lambda: migrate_languages(query, apply=True))


async def migrate_languages(query, *, apply):
    changed = 0
    for language_id, (initial_version_id, filename) in LANGUAGE_RELEASES.items():
        if query.get("_id") not in (None, language_id):
            continue
        language = await db.languages.find_one({
            **query, "_id": language_id, "latestVersionId": initial_version_id,
        })
        if language:
            print(f'{"Publish" if apply else "Would publish"}: {language_id} release 2.0')
            if apply:
                await publish_language_release(language, filename)
            changed += 1
    async for language in db.languages.find(query):
        version_id = language.get("latestVersionId")
        if not version_id:
            continue
        version = await db.language_versions.find_one({"_id": version_id, "languageId": language["_id"]})
        if version is None or version.get("kind") != "release":
            continue
        references = version.get("includedLanguageVersions", [])
        release = LANGUAGE_RELEASES.get(language["_id"])
        if release and version_id == release[0]:
            # The preview has already counted this planned seed release.
            continue
        data = await normalize_definition(version["data"], references)
        if data == version["data"]:
            continue
        changed += 1
        print(f'{"Migrate" if apply else "Would migrate"}: {language["_id"]} from {version_id}')
        if apply:
            body = CreateLanguageVersion.model_validate({
                "baseVersionId": version_id,
                "kind": "release",
                "releaseName": "Connection rule migration",
                "description": f"Canonical connection identifiers; based on {version_id}.",
                "includedLanguageVersions": references,
                "data": data,
            })
            await create_version(UUID(language["_id"]), body, User(id="connection-rule-migration", global_role="ADMIN"))
    return changed


async def publish_language_release(language, filename):
    """Publish a fixed release without replacing history or edited language tips."""
    version_id = str(uuid5(UUID(language["_id"]), "release:2"))
    data = _load_initial_data(filename)
    existing = await db.language_versions.find_one({"_id": version_id})
    if existing and (
        existing.get("languageId") != language["_id"]
        or existing.get("versionNumber") != "2.0"
        or existing.get("kind") != "release"
        or existing.get("includedLanguageVersions") != []
        or existing.get("data") != data
    ):
        raise RuntimeError(f"Existing release {version_id} differs from the migration; refusing to overwrite it.")
    await db.language_versions.update_one(
        {"_id": version_id},
        {"$setOnInsert": {
            "languageId": language["_id"], "versionNumber": "2.0",
            "createdBy": SYSTEM_OWNER_ID, "createdAt": utcnow(),
            "kind": "release", "releaseName": "Release 2.0", "description": None,
            "includedLanguageVersions": [], "data": data,
        }},
        upsert=True,
    )
    updated = await db.languages.update_one(
        {"_id": language["_id"], "latestVersionId": language["latestVersionId"], "archivedAt": None},
        {"$set": {"latestVersionId": version_id}},
    )
    if not updated.matched_count:
        raise RuntimeError(f'Language {language["_id"]} changed during migration; rerun after stopping language edits.')


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Create new releases; otherwise only report candidates.")
    parser.add_argument("--language-id", type=UUID)
    args = parser.parse_args()
    try:
        count = await migrate(apply=args.apply, language_id=args.language_id)
        print(f"{count} language(s) {'migrated' if args.apply else 'would be migrated'}.")
    except RuntimeError as error:
        parser.exit(1, f"{error}\n")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
