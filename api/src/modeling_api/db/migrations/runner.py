"""Ordered migration execution and the shared command-line interface."""

import argparse
import asyncio
from importlib import import_module
from uuid import UUID

from modeling_api.db.client import client
from modeling_api.db.migrations.registry import LANGUAGE_UPGRADE_ID, MIGRATIONS
from modeling_api.db.migrations.state import require_completed


async def migrate(*, apply=False, migration_id=None, language_id=None):
    if migration_id is not None and migration_id not in {step.identifier for step in MIGRATIONS}:
        raise RuntimeError(f"Unknown migration: {migration_id}")
    if language_id is not None and (apply or migration_id != LANGUAGE_UPGRADE_ID):
        raise RuntimeError("--language-id requires a read-only preview of the language migration.")
    for step in MIGRATIONS:
        if migration_id is not None and step.identifier != migration_id:
            continue
        if not apply and migration_id is None:
            try:
                await require_completed(*step.prerequisites)
            except RuntimeError:
                print(f"Would run {step.identifier} after {', '.join(step.prerequisites)}; "
                      "apply prerequisites before detailed preview.")
                continue
        await require_completed(*step.prerequisites)
        module = import_module(step.module)
        options = {"language_id": language_id} if language_id is not None else {}
        count = await module.migrate(apply=apply, **options)
        if apply:
            print(f"{step.identifier}: completed.")
        if migration_id == LANGUAGE_UPGRADE_ID:
            print(f"{count} language(s) {'migrated' if apply else 'would be migrated'}.")


async def main(*, migration_id=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Apply pending migrations; otherwise preview only.")
    parser.add_argument("--migration", choices=[step.identifier for step in MIGRATIONS], default=migration_id)
    parser.add_argument("--language-id", type=UUID, help="Limit the language migration's read-only preview.")
    args = parser.parse_args()
    try:
        await migrate(apply=args.apply, migration_id=args.migration, language_id=args.language_id)
    except RuntimeError as error:
        parser.exit(1, f"{error}\n")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
