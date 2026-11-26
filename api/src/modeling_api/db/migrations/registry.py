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
    Migration(
        "06_private_task_catalog",
        "modeling_api.db.migrations.versions.v06_private_task_catalog.migration",
        ("05_task_edit_history",),
    ),
    Migration(
        "07_model_activity_tracking",
        "modeling_api.db.migrations.versions.v07_model_activity_tracking.migration",
        ("06_private_task_catalog",),
    ),
    Migration(
        "08_public_case_studies",
        "modeling_api.db.migrations.versions.v08_public_case_studies.migration",
        ("07_model_activity_tracking",),
    ),
    Migration(
        "09_submissions_feedback",
        "modeling_api.db.migrations.versions.v09_submissions_feedback.migration",
        ("08_public_case_studies",),
    ),
    Migration(
        "10_language_syntax_defaults",
        "modeling_api.db.migrations.versions.v10_language_syntax_defaults.migration",
        ("09_submissions_feedback",),
    ),
    Migration(
        "11_hotel_chain",
        "modeling_api.db.migrations.versions.v11_hotel_chain.migration",
        ("10_language_syntax_defaults",),
    ),
    Migration(
        "12_laboratory_management",
        "modeling_api.db.migrations.versions.v12_laboratory_management.migration",
        ("11_hotel_chain",),
    ),
    Migration(
        "13_language_comparison_groups",
        "modeling_api.db.migrations.versions.v13_language_comparison_groups.migration",
        ("12_laboratory_management",),
    ),
    Migration(
        "14_laboratory_structure_models",
        "modeling_api.db.migrations.versions.v14_laboratory_structure_models.migration",
        ("13_language_comparison_groups",),
    ),
    Migration(
        "15_laboratory_synonym_models",
        "modeling_api.db.migrations.versions.v15_laboratory_synonym_models.migration",
        ("14_laboratory_structure_models",),
    ),
    Migration(
        "16_completion_score_categories",
        "modeling_api.db.migrations.versions.v16_completion_score_categories.migration",
        ("15_laboratory_synonym_models",),
    ),
    Migration(
        "17_help_feedback_quotas",
        "modeling_api.db.migrations.versions.v17_help_feedback_quotas.migration",
        ("16_completion_score_categories",),
    ),
    Migration(
        "18_game_development",
        "modeling_api.db.migrations.versions.v18_game_development.migration",
        ("17_help_feedback_quotas",),
    ),
    Migration(
        "19_initialize_dashboard",
        "modeling_api.db.migrations.versions.v19_initialize_dashboard.migration",
        ("18_game_development",),
    ),
    Migration(
        "20_remove_user_profiles",
        "modeling_api.db.migrations.versions.v20_remove_user_profiles.migration",
        ("19_initialize_dashboard",),
    ),
    Migration(
        "21_task_help_feedback",
        "modeling_api.db.migrations.versions.v21_task_help_feedback.migration",
        ("20_remove_user_profiles",),
    ),
    Migration(
        "22_help_choice_labels",
        "modeling_api.db.migrations.versions.v22_help_choice_labels.migration",
        ("21_task_help_feedback",),
    ),
    Migration(
        "23_epk_language",
        "modeling_api.db.migrations.versions.v23_epk_language.migration",
        ("22_help_choice_labels",),
    ),
)
