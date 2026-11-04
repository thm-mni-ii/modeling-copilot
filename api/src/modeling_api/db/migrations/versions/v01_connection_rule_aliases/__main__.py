"""Language migration CLI; preview only without --apply."""

import asyncio

from modeling_api.db.migrations.registry import LANGUAGE_UPGRADE_ID
from modeling_api.db.migrations.runner import main

if __name__ == "__main__":
    asyncio.run(main(migration_id=LANGUAGE_UPGRADE_ID))
