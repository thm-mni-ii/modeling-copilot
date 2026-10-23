# Learning paths

Tasks are still created under `/tasks`. Administrators organize task releases into
learning path templates under `/learning-path-templates`. Learners start personal
runs under `/learning-path-runs`. Each learner has one resumable run per template.

## Treasure journey

The personal run displays tasks as interactive treasure chests on an island map.
The landscape progresses from Palm Beach through Rocky Island to Treasure Mountains;
these regions do not indicate task difficulty. Narrow layouts use a vertical path.

Clicking a station or activating it with the keyboard opens its task model directly.
Locked stations cannot be activated and do not reveal challenge text. Their
prerequisites appear in the tooltip and accessible label. Connections to locked
stations use a gray dashed line and a lock marker. Icons accompany all status colors.
The pirate marks the last selected station; its visual position is optionally kept
in session storage for each run.

Each currently completed task counts as one coin. Reopening a model adds no coins.
The counter uses existing progress data and requires no separate currency system.
Completing a task from the map triggers a brief coin animation. Newly available
stations are highlighted once. Reduced-motion preferences disable these animations.

## Editing templates

Add tasks, reorder them using drag-and-drop or the up/down controls, and configure
unlock rules per step. New steps require the previous step to be completed by
default; this rule can be removed. Display order alone does not restrict access.

Templates are not versioned: changes appear in existing runs. `updatedAt` only
prevents concurrent edits from overwriting each other. Stable step IDs preserve
progress and model assignments when reordering. Removed steps and their work are
retained but hidden. Removed step IDs cannot be reused. Rules referencing a step
must be updated before that step can be removed.

Publishing requires at least one step and accessible, published task releases.
Archived or unpublished templates cannot start new runs; existing runs remain
accessible.

## Unlock rules

`unlock.mode` is `all` (AND) or `any` (OR). An empty condition list unlocks a step
immediately. Each step has its own rules:

| `type` | Fields | Meaning |
| --- | --- | --- |
| `completed` | `stepId` | A prerequisite task has been completed |
| `score` | `stepId`, `value` (0-100) | Reserved minimum-score condition |
| `at` | `at` (ISO timestamp with offset), `timezone` (IANA) | Fixed unlock time |
| `after` | `seconds`, optional `stepId` | Delay after run start or another step's completion |

Times are evaluated by the server. The editor explicitly shows the browser timezone
and stores an unambiguous timestamp. The run view refreshes every 30 seconds and on
manual refresh. Missing references and dependency cycles are rejected. Previously
granted access remains available after later rule changes.

**Scoring is not connected yet.** A `score` condition remains unsatisfied regardless
of manual task completion. An OR alternative can still unlock a step. There is no
endpoint for submitting arbitrary percentage values.

## Challenges

Each step may have one optional challenge with a type, title, description, MDI icon,
and optional hex color. `solo` encourages independent work, `time` defines a time
budget in seconds, and `help_budget` defines a target number of internal hints.
Type-specific parameters are only accepted for the corresponding challenge type.
Challenges do not restrict help, model editing, or task completion.

The map shows the configured challenge icon. Before the first task start, a dialog
explains the challenge. Canceling creates no model and starts no timer. The start
endpoint accepts `acknowledgedChallenge` containing the displayed settings. They
must match the current settings when starting a new task, otherwise the API returns
409. Tasks without a challenge require no acknowledgement.

The step run stores the acknowledged configuration in `challenge.config` and the
server start time in `challenge.startedAt`. Time challenges also have a planned
`endsAt` and an optional `stoppedAt` for an early manual end. Reopening resumes the
same attempt. Template changes only affect tasks that have not started yet; a task
started without a challenge does not gain one retroactively.

A collapsible overlay in the model editor displays the goal and description.
The countdown uses the server deadline and continues while switching tabs or closing
the editor. Expiry only displays a message; it does not terminate or complete the
task. "End time challenge" stores an early stop permanently. Repeating the action
does not reset the timestamp, and the task remains editable.

Help usage, research events, and a new task-completion mechanism are not implemented.
Solo and Help Budget display the learning goal or target budget, not a measured
usage count. No rewards are tied to avoiding help.

## Models and progress

Starting a step creates a model with the selected task release, required workspace
languages, and an initial model version. Repeated or simultaneous starts open the
same model. The step run stores `runId`, `stepId`, `modelId`, title, start time,
task reference, and challenge state. Models store no learning-path or challenge
metadata; their `taskVersion` remains fixed as with "From Task". The editor loads
the step run by model ID. Ordinary models return a `null` context.

General model lists exclude models referenced by step runs, including task and
archive filters. Exclusion happens before counting and pagination. Referenced
models cannot be hard-deleted. They are opened from their learning path. The editor
can save and return to the run or complete the task. Manual completion does not
satisfy a minimum-score condition. Progress reflects currently visible steps, so
adding tasks can reduce the percentage without resetting previous completions.

## API

- `GET/POST /v1/learning-path-templates`: List or create templates.
- `GET/PUT /v1/learning-path-templates/{id}`: Read or replace a template.
- `POST /v1/learning-path-templates/{id}/runs`: Start or resume a personal run.
- `GET /v1/learning-path-runs` and `GET /v1/learning-path-runs/{id}`: Read personal runs.
- `POST /v1/learning-path-runs/{id}/steps/{stepId}/start`: Create or resume a task model.
- `POST /v1/learning-path-runs/{id}/steps/{stepId}/complete`: Complete a task.
- `GET /v1/learning-path-step-runs/by-model/{modelId}`: Read the editor context.
- `POST /v1/learning-path-runs/{id}/steps/{stepId}/challenge/stop`: End a time challenge early.

Template writes require the global administrator role. Runs and models are scoped
to the authenticated owner. MongoDB indexes are created at API startup. Legacy
learning-path and challenge metadata is moved from models into step runs
idempotently, preserving original times and completions. Old model fields are
removed only after successful transfer.

## Initial data and English defaults

The Order Management example has six sequential steps: the three existing tasks
with Solo, Time, and Help Budget challenges, followed by the same tasks for review.
The time budget is 15 minutes; the help target is three internal hints. Initial
seeding creates configuration only, never personal runs or running timers.
The example is validated against the API template schema before insertion.
Reseeding preserves edited templates and ongoing attempts. The untouched older
three-step example is upgraded automatically.

All interface text and initial example text is written directly in English in the
source code. No translation files, localization layer, or automatic text translation
are included. Existing stored text is preserved when reseeding.
