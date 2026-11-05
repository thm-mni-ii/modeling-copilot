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

7. `versions/v06_private_task_catalog/migration.py` makes all current tasks private
   in the shared catalog without changing task contents or historical releases.

8. `versions/v07_model_activity_tracking/migration.py` creates indexes for editor
   sessions and their related interactions. It does not backfill data or modify model
   and task histories; see [Model activity tracking](model-activity-tracking.md).

9. `versions/v08_public_case_studies/migration.py` publishes the ten case studies
   from pages 5-14 of `02_1_hausübung.pdf` (first database homework, winter semester
   2026/2027): Einzelhandel, Paketversand, Mühle, Ticketverkauf, Pflegedienst,
   Bauunternehmen, Messeverwaltung, Hundeschule, Escaperoom and Abfallwirtschaft.
   Names use `F<number> – <designation>` (F1 through F10). Each public task has an immutable 1.0 release,
   the complete case-study text and control questions, SERM 2.0 as its required
   modeling language, and informative feedback as its default autonomy mode.
   The extracted content and fixed IDs live in
   `versions/v08_public_case_studies/case_studies.json`. Preview is read-only;
   conflicting IDs stop the migration before content is inserted. Retries reuse
   matching documents; completed migrations preserve subsequent administrator
   changes. Existing tasks and learning paths remain unchanged.

   Verification on 2026-11-04 compared all ten extracted texts and 49 control
   questions with the PDF and validated their task/release schemas. An isolated
   MongoDB 4.4.29 run verified the prerequisite chain, read-only preview, missing
   language and conflicting-ID failures, retry after a partially inserted release,
   public access for non-admin users, informative feedback, and preservation of
   existing data and later administrator edits. No live database was changed.

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

Deploy the new API image together with the updated `k3s-portainer.yaml`. Its
`Recreate` strategy stops the old API before the new pod's `database-backup`
init container exports the `MONGODB_DATABASE` database. Only a successful backup
allows the API container to start its existing migrations and then Uvicorn.
This introduces a maintenance interval. Keep other direct database writers
stopped throughout backup and migration. Do not use manual pod deletion or
additional API replicas for releases: those do not provide the same write stop
as a Deployment update with `Recreate`.

Select immutable release tags or image digests for API and web in Portainer,
and record the previous image digests before deploying. The manifest defaults
to `latest`; pulling it is not enough to identify a rollback image or to trigger
a new Deployment rollout. Explicitly redeploy when using an unchanged image
reference. Do not override the image's startup command with direct Uvicorn.

### Automatic pre-migration backup in Portainer / k3s

The backup script and its settings are included in the manifest's
`modeling-copilot-backup` ConfigMap, so Portainer needs no host checkout or
separate command. Set `BACKUP_RELEASE_VERSION` there to the intended release
tag for readable archive names. It is only a label, never a backup reuse key.
Changing this ConfigMap alone does not trigger an API rollout.

Each new API pod creates a backup, even when the version was not updated:

```text
/backups/pod-<pod-uid>/
  modeling_v1.2.3_20261104T143015Z.archive.gz
  SHA256SUMS
  metadata.txt
```

Names contain the configured version and the actual UTC date and time. The
pod UID distinguishes backups even within the same second. An unset/empty
version is labeled `unversioned`; the shipped default is `latest`.

The dump includes all collections, indexes and migration records of the
application database. The script checks the dump exit status, archive size,
gzip integrity and SHA-256 checksum before publishing its staging directory
atomically. Authentication, storage or verification failures block API startup
and therefore migration. Kubernetes retries the failed init container.

If the init container runs again for the same pod, it verifies and reuses that
pod's completed backup. An invalid existing backup blocks startup. A new pod
always creates another backup and retains all earlier ones, including the
original backup from before a failed migration. After a failure, use logs and
timestamps to identify that original backup: a later pod may have backed up
partially migrated data. Hidden `.partial-*` directories are incomplete attempts
and must not be used for recovery.

Archives persist on the separate `modeling-copilot-backups` PVC (initial request:
10 GiB). Only the init container mounts it; the API container cannot modify it.
There is no automatic deletion. Monitor actual free disk space, export backups
and remove obsolete archives/incomplete attempts deliberately. A full disk
blocks the release. The `local-path` storage is node-local and does not protect
against losing that node; copy successful archives to independent storage for
that protection. Do not delete the backup PVC or its namespace during recovery.

Inspect the backup step before investigating migration startup:

```sh
kubectl -n modeling-copilot logs <api-pod> -c database-backup
kubectl -n modeling-copilot describe pod <api-pod>
```

This safeguard applies to the API deployment in `k3s-portainer.yaml`. Direct
migration CLI calls and local Docker Compose still require a manual backup
with application writes stopped. `collab_kit` is a separate database and is not
included; a complete application rollback needs its own coordinated backup and
write stop if Collab-Kit data must also be restored. No automatic restore occurs.

The first start adopts the old baseline, adds missing seeds, publishes language
releases, and then serves requests. Verify migration logs and `/health/ready`
before reopening access. Keep other direct database writers stopped during the
upgrade. For local Compose upgrades, stop the old API before `up --build` as well.

If a release must be rolled back, stop the API and restore the pre-release
database backup together with its matching previous image. Reverting only the
image does not revert newly published language releases.

### Manual database restore

Before the first production release, rehearse backup and restore against an
isolated database. Archive integrity checks alone do not prove restorability.

For recovery, scale the API to zero in Portainer and pause any deployment
automation and other database writers. Select the original pre-migration
backup and the matching previous API/web images. For access to the backup PVC,
create a temporary recovery pod in the same namespace using this specification
(it is deliberately not part of the normal release manifest):

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: database-recovery
  namespace: modeling-copilot
spec:
  restartPolicy: Never
  containers:
    - name: tools
      image: mongo:4.4.29
      command: ["sleep", "infinity"]
      envFrom:
        - secretRef:
            name: modeling-copilot-api-secrets
        - configMapRef:
            name: modeling-copilot-config
      volumeMounts:
        - name: backups
          mountPath: /backups
          readOnly: true
  volumes:
    - name: backups
      persistentVolumeClaim:
        claimName: modeling-copilot-backups
```

Open a shell with `kubectl -n modeling-copilot exec -it database-recovery -- sh`.
Choose the backup directory, inspect its metadata and verify it:

```sh
cd /backups/pod-<original-pod-uid>
cat metadata.txt
sha256sum -c SHA256SUMS && gzip -t ./*.archive.gz
```

Stop if either verification fails. After confirming the database name and that
all writers are stopped, restore with the following commands **inside that
shell**. This explicitly deletes the current application database first, so
collections introduced by the failed migration cannot survive the restore.
The original backup remains read-only. Restore into an isolated database first
if the backup has not yet been rehearsed.

```sh
set -eu
: "${MONGODB_DATABASE:?}" "${DB_USER:?}" "${DB_PASSWORD:?}"
mongo --host mongo:27017 --username "$DB_USER" --password "$DB_PASSWORD" \
  --authenticationDatabase admin "$MONGODB_DATABASE" \
  --eval 'if (!db.dropDatabase().ok) quit(1)'
mongorestore --host mongo:27017 --username "$DB_USER" --password "$DB_PASSWORD" \
  --authenticationDatabase admin --archive="$(find . -name '*.archive.gz')" \
  --gzip --stopOnError
```

Verify the restore completed successfully. Configure the recorded previous
images while API replicas remain at zero, then remove the recovery pod
(`kubectl -n modeling-copilot delete pod database-recovery`) to release the
backup volume. Scale the API back to one and check migration logs and
`/health/ready` before reopening access. Never delete the PVC as cleanup.

Backup verification on 2026-11-04 used the manifest's actual script with an
isolated MongoDB 4.4.29 container. It covered same-pod reuse, a fresh backup for
a new pod with the same version, an empty database, an unset version, invalid
credentials, read-only storage and a corrupted existing backup. Restoring the
original archive recovered documents, a unique index and migration records,
and removed a collection introduced after the backup. Temporary containers,
volumes and the network were removed. No live cluster rollout was performed.

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
