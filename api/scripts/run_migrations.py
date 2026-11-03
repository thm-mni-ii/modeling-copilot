"""Command-line entry point; preview only without --apply."""

import asyncio

from modeling_api.db.migrations.runner import main

if __name__ == "__main__":
    asyncio.run(main())
