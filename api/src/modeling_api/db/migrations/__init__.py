"""Migration state and prerequisites shared with application startup."""

from modeling_api.db.migrations.registry import BASELINE_ID, LANGUAGE_UPGRADE_ID, MIGRATIONS
from modeling_api.db.migrations.state import require_completed, run_migration


async def require_current():
    """Require every registered release step before accepting API requests."""
    await require_completed(*(migration.identifier for migration in MIGRATIONS))
