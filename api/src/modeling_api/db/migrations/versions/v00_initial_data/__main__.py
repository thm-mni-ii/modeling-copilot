"""Baseline migration CLI; preview only without --apply."""

import asyncio

from modeling_api.db.migrations.registry import BASELINE_ID
from modeling_api.db.migrations.runner import main

if __name__ == "__main__":
    asyncio.run(main(migration_id=BASELINE_ID))
