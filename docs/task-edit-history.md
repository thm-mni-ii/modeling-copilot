# Task editing history

Task edits belong to a model's permanently assigned task release. Their history is
independent of model checkpoints, releases, and modeling languages.

## Local editing and recovery

Every document change produces an action ID, creation time, and RFC 6902 JSON
patch. The workspace journal in localStorage contains the saved task document,
pending patches, and the latest local preview alongside the model draft. No task
editing requests run automatically. Save publishes the pending actions as a batch.
Save sends bounded batches sequentially. Edits made during a save remain pending
and recoverable until the next save.

The recovery dialog previews the task above the drawing when a task is assigned.
If the server's model version has changed, only the independent task draft can be
restored. Already committed action IDs are excluded when recovering after a lost
response. A task restore is itself a new local action, preserving the saved history.

## Database collections

- `models.taskEditVersionId` and `models.taskEditRevision` identify the published
  task state. No editable task document is stored on the model.
- `task_edit_versions`: immutable checkpoint batches containing ordered `patches`.
  Each action stores its ID, revision, client creation time, digest, operations,
  and a summary of created, removed, or changed edit IDs exactly once. The batch
  stores the model, actor, save time, `previousVersionId`, and `baseReleaseId`.
  Its ID is the last action ID in the batch. Checkpoints contain no full document.
- Automatic `release` records additionally contain the complete `document`.
  They are created after **500 actions or 256,000 UTF-8 JSON bytes** of operations
  and change summaries since the previous release, whichever occurs first.
  Counters continue across saves. A save crossing a threshold is split there;
  remaining actions start a new release phase. Counters reset at each release.
  The immutable task release is the initial base and is not duplicated.
- `model_versions.taskEditVersionId`: a reference to the task state at the time of
  the model save, explicitly selected by the saving client. The API materializes
  `taskEditSnapshot` for previews.

Publishing inserts the immutable records before atomically updating the model's
head with optimistic concurrency. Only batches reachable from that head are listed
or accessible through the history API. This supports standalone MongoDB without
multi-document transactions: interrupted batches are unpublished, and retrying
the same action IDs and content is idempotent. Competing saves return HTTP 409;
the client retains its local journal. Unpublished records are retained for retry.

The API reconstructs a state from its base release and the ordered patches up to
the requested action revision. A release's final state loads directly. Historical
actions inside a batch, including inside a release batch, remain individually
addressable by their original action IDs. Phase records are fetched together;
predecessor pointers exclude unpublished competing branches. Replay copies the
base document once, rather than once per action. History queries load action
metadata without full documents or patch operations. API response shapes and the
per-action timeline stay unchanged; technical releases do not add extra UI steps.

Existing task edits are not read or converted. Migration `05_task_edit_history`
discards all earlier task-edit data and initializes the new structure; see
[Database setup and releases](database-migrations.md).

## Replay benchmark and release threshold

Measured locally on 2026-11-04 using Python 3.13 and MongoDB in Docker, in a
temporary isolated database. Representative generated Tiptap documents contained
20, 200, or 2,000 paragraphs. Actions changed a highlight color and included
normal history summaries; checkpoints contained 25 actions. Automatic releases
were deliberately omitted to measure increasing replay lengths. Each case used
one warm-up and 20 measured loads through `snapshot`, including MongoDB reads,
BSON decoding, patch conversion, and reconstruction. Times below are p95 in ms:

| Document (BSON) | 100 actions | 500 actions | 1,000 actions | 5,000 actions |
| --- | ---: | ---: | ---: | ---: |
| 11 KB | 4.07 | 7.68 | 11.97 | 50.32 |
| 109 KB | 6.09 | 9.09 | 11.35 | 50.77 |
| 1.09 MB | 16.87 | 21.47 | 24.20 | 63.49 |

Pure patch conversion/replay at 500 actions took 1.26–5.93 ms p95. The 500-action
cap leaves headroom against a 50 ms storage/reconstruction budget in these cases;
the byte cap additionally bounds larger operations and summaries. These are
local representative measurements, not an HTTP latency or production guarantee.
Single-action saves, larger patch payloads, and different infrastructure can
cost more; the constants are centralized in `services/task_edit_history.py`.
The byte threshold is checked after an action, so one large action can exceed it
and immediately creates a release.

## Documents and timelines

The API imports task HTML into canonical JSON and returns `contentDocument` with
the task version. The editor consumes this JSON. Validation removes user edit
marks and insertions, normalizes editor defaults, and compares the result with the
same canonical base document. Original content and formatting remain immutable.
Array patches retain unchanged prefixes and suffixes and use indexed add/remove
operations when lengths change. Adding one paragraph to 1,000 paragraphs produces
one small add operation instead of replacing the complete paragraph array.

The task timeline includes saved and pending actions. The model timeline can
optionally interleave task actions. Restoring a model keeps the current task edits
unless the user explicitly chooses the previewed task state.
