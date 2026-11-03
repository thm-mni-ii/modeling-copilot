# Database setup and releases

The API image applies `api/scripts/run_migrations.py --apply` before starting
Uvicorn. Docker Compose and the k3s deployment therefore use the same setup.
Running Uvicorn directly requires running this command first with `PYTHONPATH=api/src`
and the intended `MONGODB_URI` and `MONGODB_DATABASE` environment variables.

## Code organization

```text
api/scripts/                         Thin CLI entry points (existing commands stay valid)
api/src/modeling_api/db/
  client.py                         MongoDB connection and index creation
  store.py                          Shared persistence helpers
  help_questionnaires.py            Stable questionnaire identities used at runtime
  migrations/
    registry.py                     Ordered steps, immutable IDs and prerequisites
    state.py                        Execution records, locking and retry handling
    runner.py                       Execution and shared CLI options
    resources.py                    Shared reader for prefix-owned JSON resources
    versions/
      v00_initial_data/
        migration.py                Baseline validation, initialization and adoption
        definitions.py              Reads identities and references from manifest.json
        initial_data.py             Idempotent document writing and revision guards
        manifest.json               Identities, examples and entry-course bindings
        learning_paths.json         Full learning paths, steps and challenges
        example_surveys.json        Example questionnaire and pulse definitions
        entry_pulse_surveys.json    Entry-course pulse definitions
        ...json                     Languages, tasks, sample model and questionnaires
      v01_connection_rule_aliases/
        migration.py                Language upgrade logic
        releases.json               Language/release resource assignments
        erm_v2.json                 ERM 2.0 definition
        serm_v2.json                SERM 2.0 definition
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
docker compose run --rm --no-deps api python scripts/run_migrations.py
```

Build the new API image first and start MongoDB if necessary. Overriding the
container command as above bypasses automatic application. Before baseline
adoption, the combined preview validates the old baseline and reports the
subsequent step as pending. A detailed language preview is available after
`00_initial_data.py --apply` via `01_migrate_connection_rule_aliases.py`.
Both numbered commands remain available as thin wrappers. Alternatively, select
a step through the shared entry point, for example:

```sh
python api/scripts/run_migrations.py --migration 01_connection_rule_aliases
python api/scripts/run_migrations.py --migration 01_connection_rule_aliases --language-id b20cd790-923c-4c79-b308-e154cdad331b
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
