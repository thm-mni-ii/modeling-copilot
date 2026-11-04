"""Single ordered registry for execution and API startup prerequisites.

Migration identifiers are persisted in MongoDB and must never be renamed.
Register new steps here explicitly; merely adding a Python file does not run it.
"""

from dataclasses import dataclass

BASELINE_ID = "00_initial_data"
LANGUAGE_UPGRADE_ID = "01_connection_rule_aliases"


@dataclass(frozen=True)
class Migration:
    identifier: str
    module: str
    prerequisites: tuple[str, ...] = ()


MIGRATIONS = (
    Migration(BASELINE_ID, "modeling_api.db.migrations.versions.v00_initial_data.migration"),
    Migration(
        LANGUAGE_UPGRADE_ID,
        "modeling_api.db.migrations.versions.v01_connection_rule_aliases.migration",
        (BASELINE_ID,),
    ),
    Migration(
        "02_seminar_management",
        "modeling_api.db.migrations.versions.v02_seminar_management.migration",
        (LANGUAGE_UPGRADE_ID,),
    ),
    Migration(
        "03_update_survey",
        "modeling_api.db.migrations.versions.v03_update_survey.migration",
        ("02_seminar_management",),
    ),
    Migration(
        "04_maintenance_management",
        "modeling_api.db.migrations.versions.v04_maintenance_management.migration",
        ("03_update_survey",),
    ),
    Migration(
        "05_task_edit_history",
        "modeling_api.db.migrations.versions.v05_task_edit_history.migration",
        ("04_maintenance_management",),
    ),
)
