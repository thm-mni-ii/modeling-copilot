# Database setup and releases

The API image runs `python -m modeling_api.db.migrations --apply` before starting
Uvicorn. Docker Compose and the k3s deployment therefore use the same setup.
Running Uvicorn directly requires running this command first with `PYTHONPATH=api/src`
and the intended `MONGODB_URI` and `MONGODB_DATABASE` environment variables.

## Code organization

```text
api/src/modeling_api/db/
  client.py                         MongoDB connection and index creation
  store.py                          Shared persistence helpers
  help_questionnaires.py            Stable questionnaire identities used at runtime
  migrations/
    __main__.py                     Shared CLI entry point (python -m modeling_api.db.migrations)
    registry.py                     Ordered steps, immutable IDs and prerequisites
    state.py                        Execution records, locking and retry handling
    runner.py                       Execution and shared CLI options
    resources.py                    Shared reader for prefix-owned JSON resources
    versions/
      v00_initial_data/
        __main__.py                 Baseline-only CLI entry point
        migration.py                Baseline validation, initialization and adoption
        definitions.py              Reads identities and references from manifest.json
        initial_data.py             Idempotent document writing and revision guards
        manifest.json               Identities, examples and entry-course bindings
        learning_paths.json         Full learning paths, steps and challenges
        example_surveys.json        Example questionnaire and pulse definitions
        entry_pulse_surveys.json    Entry-course pulse definitions
        ...json                     Languages, tasks, sample model and questionnaires
      v01_connection_rule_aliases/
        __main__.py                 Language-upgrade-only CLI entry point
        migration.py                Language upgrade logic
        releases.json               Language/release resource assignments
        erm_v2.json                 ERM 2.0 definition
        serm_v2.json                SERM 2.0 definition
      v05_task_edit_history/
        migration.py                Discards legacy task edits, initializes the new history
```

The API startup check and migration runner share `registry.MIGRATIONS`.
Each migration prefix owns its Python helpers and JSON content in one directory;
there is no separate `seeds` namespace. Initial content, including the previously
Python-generated learning paths, challenges and pulse questions, lives in JSON.
The Python helpers load/validate the data, write documents and retain the existing
revision guards. The shared resource reader is also used by the runtime help
questionnaire service without importing migration implementations.

## Ordered steps

1. `versions/v00_initial_data/migration.py` initializes an empty database. For an existing database,
   it first validates the UML and Order Management baseline shipped on `main`,
   then adds the missing ERM/SERM languages, examples, surveys and learning paths.
   Existing task/model names, ownership, visibility and historical releases are
   preserved. Versioned entry-course/questionnaire upgrades retain the existing
   seed revision guards that protect later admin changes.
2. `versions/v01_connection_rule_aliases/migration.py` publishes ERM/SERM 2.0 for untouched
   initial language tips and normalizes other current language releases when
   necessary. It creates new releases and moves the current language pointer;
   historical language releases, task references and learner models stay pinned.
   Archived languages and newer canonical admin releases are preserved.
3. `versions/v02_seminar_management/migration.py` adds the annotated task
   “Seminarverwaltung – SERM” to “Grafische Datenmodellierung”, directly after
   “Hilfe bei Datenmodellierungsaufgaben”. The task pins SERM 2.0 from
   `01_connection_rule_aliases`.
   Existing steps and personal progress are
   preserved. Preview is read-only; retries reuse fixed task, release and step
   IDs and reject conflicting content.
4. `versions/v03_update_survey/migration.py` publishes shortened task
   completion questionnaires for Bestellabwicklung and Seminarverwaltung with
   simplified support choices. The questions about the help button, pirate
   prompts and study incentives move to a required “Abschluss: Studienteilnahme”
   station directly after Seminarverwaltung. Existing questionnaire releases
   and submitted answers are preserved; new sessions use the new releases.
   The seminar completion also asks whether the task could have been solved
   without support, followed by a ranking of the support sources actually used.
   Learners may instead say that none is dispensable or that they cannot judge.
   Sorting is skipped when fewer than two sources were selected.

5. `versions/v04_maintenance_management/migration.py` adds the annotated task
   “Wartungsverwaltung – SERM” between Seminarverwaltung (station 5) and the
   final study questionnaire (previously station 6). It pins the same SERM 2.0
   release and reuses the integrated seminar completion questionnaire.
   Only object types are annotated; learners determine attributes, keys and
   cardinalities themselves. Multiple executions by the same technician on
   the same maintenance order remain distinct. Preview is read-only; fixed
   identities and conflict checks allow retries without overwriting edits.

6. `versions/v05_task_edit_history/migration.py` discards all earlier task-edit
   data, as the editing mode was never in production use. It removes
   `models.taskEdit`, `models.taskEditBaseSignature`,
   `model_versions.taskEditSnapshot`, any other legacy `taskEdit*` fields, and
   indexes on them. It also drops the collections `task_edit_events`,
   `task_edit_documents` and `task_edit_versions`, and clears embedded
   `submissionSnapshot.taskEditSnapshot` copies in evaluations (the evaluations
   themselves remain). Afterwards `models.taskEditVersionId` is `null`,
   `models.taskEditRevision` is `0`, `model_versions.taskEditVersionId` is `null`
   (no dangling references), and the two `task_edit_versions` indexes exist.
   No empty documents or artificial edits are created. Task texts, models,
   model versions, languages and learning paths are untouched; no
   `contentDocument` backfill is needed because task loading derives it from
   `contentHtml` when absent, so original content and task element/connection
   annotations are preserved. Preview lists affected documents and indexes
   without writing. The completed record prevents later starts from deleting
   new task edits.

`schema_migrations` records each step as `running`, `failed`, or `completed`.
The API refuses startup until all registered steps have completed. Repeated starts skip
completed steps. Concurrent claims fail instead of executing a step twice.
New migrations must be added explicitly to `MIGRATIONS` in
`db/migrations/registry.py`, with their own immutable ID, importable module and
prerequisites. This also adds them to the API startup check; no second list needs
updating. Each module exposes `async migrate(*, apply=False)`. The existing IDs
`00_initial_data` and `01_connection_rule_aliases` have not changed during the
directory reorganization. Changing an already completed step does not apply it
again to an existing database. Freeze existing migration behavior and resources;
ship subsequent data changes as new registered steps.

## Preview

Without `--apply`, all scripts are read-only:

```sh
docker compose run --rm --no-deps api python -m modeling_api.db.migrations
```

Build the new API image first and start MongoDB if necessary. Overriding the
container command as above bypasses automatic application. Before baseline
adoption, the combined preview validates the old baseline and reports the
subsequent step as pending. A detailed language preview is available after
`python -m modeling_api.db.migrations --migration 00_initial_data --apply`.
All CLI entry points live inside the migration package. Individual steps can be
run as version modules, for example
`python -m modeling_api.db.migrations.versions.v01_connection_rule_aliases`,
or selected through the shared entry point. For local commands below, set
`PYTHONPATH=api/src` first:

```sh
python -m modeling_api.db.migrations --migration 01_connection_rule_aliases
python -m modeling_api.db.migrations --migration 01_connection_rule_aliases --language-id b20cd790-923c-4c79-b308-e154cdad331b
```

Do not execute the preview against a database while another migration is running.

## Production release from main

Use a database backup taken with application writes stopped. Deploy the new API
image together with the updated `k3s-portainer.yaml`. Its `Recreate` strategy
stops the old API before the new container migrates the database; this introduces
a maintenance interval. A restart of an old image does not deploy the new code:
verify the selected release image/digest. Do not override the image's startup
command with a direct Uvicorn invocation.

The first start adopts the old baseline, adds missing seeds, publishes language
releases, and then serves requests. Verify migration logs and `/health/ready`
before reopening access. Keep other direct database writers stopped during the
upgrade. For local Compose upgrades, stop the old API before `up --build` as well.

If a release must be rolled back, stop the API and restore the pre-release
database backup together with its matching previous image. Reverting only the
image does not revert newly published language releases.

## Failures and recovery

An incompatible or incomplete old baseline stops the upgrade before adding seed
data. Conflicting fixed language releases are never overwritten. A caught error
marks the step `failed`; after correcting the reported cause, rerun the runner
or restart the container. Completed steps are skipped, failed idempotent steps
resume. An interrupted empty-database initialization retains its initialization
mode so that partial seeds can be completed.

A process killed without exception handling can leave `running` behind. Stop
all migration/API processes, inspect the recorded ID and the underlying data,
then explicitly mark only that abandoned record `failed` before retrying. Never
delete all migration records or reset a database to recover a production upgrade.
For example, in a MongoDB shell connected to the intended database, after
confirming that the baseline worker has stopped:

```javascript
db.schema_migrations.updateOne(
  {_id: "00_initial_data", status: "running"},
  {$set: {status: "failed"}}
)
```

This retains the initialization mode needed for a safe retry. No automatic
timeout steals a potentially active migration's lock.

## Verification (2026-11-03)

Runtime checks used disposable MongoDB 8.0 and 4.4.29 containers without
production data or shared volumes. The upgrade source was the actual seed code
and JSON files from `main` at `9cb1fac3a3bd0f55318ca431976ffa81ebb1a580`.
All ten scenarios passed against both MongoDB versions:

| Scenario | Verified result |
| --- | --- |
| Empty database | Preview writes nothing; setup completes; repeat changes nothing |
| Main baseline with admin edits and learner data | Existing records/releases remain intact; new seeds/releases are added |
| Unrecorded branch baseline | Adoption works; archived languages and newer canonical admin tips survive |
| Incompatible populated database | Baseline fails; language migration and API startup are blocked |
| Interrupted initialization | Failed initialization retains mode and resumes successfully |
| Conflicting fixed language release | Conflicting content survives; retry succeeds after correcting the conflict |
| Concurrent claims | Only one action executes; completed action is skipped |
| API startup prerequisites | Startup fails before migration and succeeds after completion |
| Interrupted main adoption | Partial additions can be resumed without duplicate seeds |
| Interrupted language upgrade and abandoned lock | ERM publication survives retry; running lock requires explicit recovery |

These scenarios were rerun successfully after the directory reorganization.
Additional checks confirmed compatibility of the numbered CLI wrappers,
single-step selection, filtered read-only previews, and the module entry point.
All 13 moved JSON resources matched their original contents. AST comparisons
confirmed unchanged execution/locking logic and unchanged seed-writing actions
apart from reader names and the previously documented metadata-preservation fix.

After grouping resources by prefix and extracting generated content into JSON,
all 70 initial documents were compared with the previous implementation. IDs,
references, content and revisions matched exactly; only runtime timestamps were
normalized for comparison. The scenario and container checks were repeated for
the prefix-specific layout.

The built Python 3.13 API image also initialized an empty MongoDB 8.0 database
and upgraded a main baseline on MongoDB 4.4.29 using its default container
command. Both returned HTTP 200 from `/health/ready`, including after restart;
completed migration records stayed unchanged. An incompatible database caused
the container to exit with code 1 before Uvicorn started. The k3s manifest was
parsed and its API `Recreate` strategy verified; no live cluster rollout was
performed. The isolated test containers were removed after verification.
