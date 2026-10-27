# Lernpfade und Fragebögen: Konzept

## 1. Ist-Zustand

Code: `api/src/modeling_api/services/learning_paths.py`, `learning_path_store.py`,
`schemas/learning_path_documents.py`, Seed-Daten in `db/initial_data.py`.

| Collection | Inhalt |
| --- | --- |
| `learning_path_templates` | Metadaten **und** eingebettetes Array `steps[]` (Aktivität, Unlock-Regeln, Vor-/Nach-Fragebogen, Challenge), `revision`, `retiredStepIds[]` |
| `learning_path_runs` | `learnerId`, `templateId`, eingebettetes Array `stepStates[]` (Fortschritt, `modelId`, Challenge-Zeiten, Session-Referenzen) |
| `survey_sessions` | Antworten, Status, `releaseId` (ohne Rückverweis auf Run/Step) |
| `models` | Modell zum Task-Step; Zuordnung nur indirekt über `runs.stepStates.modelId` |

Probleme:

1. **Steps sind keine Entitäten.** Sie existieren nur als Array-Element im Template; keine eigene
   Collection, keine eigenen Indizes, keine Integrität.
2. **Run-Steps sind eingebettet.** Wachsende Arrays, Updates über `stepStates.$` und
   `$elemMatch`-Guards, uneinheitliche Felder für Task- und Survey-Steps.
3. **Entfernen über `retiredStepIds`.** Ein entfernter Step ist nicht mehr auffindbar; laufende
   Run-Steps zeigen ins Leere.
4. **`revision` + `require_current_template` blockieren Lernende** bei jeder Template-Änderung.
5. **Kein Änderungsvertrag.** Release, Vor-/Nach-Fragebogen und Challenge können sich unter einem
   laufenden Step ändern; die Challenge wird nicht am Run-Step festgehalten.
6. **Reihenfolge nur implizit** über manuell gepflegte Unlock-Bedingungen.
7. **`finished`/Fortschritt** ohne Regel für nachträglich hinzukommende oder archivierte Steps.
8. **Fortschritt von Survey-Steps wird aus Sessions abgeleitet,** nicht gespeichert (zwei Wahrheiten).

## 2. Ziel-Datenmodell

Referenzen statt Einbettung für Dinge mit eigener Identität und Lebensdauer (Steps). Eingebettet
bleibt, was nur zu genau einem Besitzer gehört (Unlock-Regeln, Challenge-Konfiguration).

```text
learning_path_templates        learning_path_template_steps
  _id                            _id (= stepId, unveränderlich)
  title, description             templateId
  status: draft|published|       kind: task | survey
          archived               title
  stepIds: [stepId, ...]  ---->  unlock {mode: sequence|all|any,
  revision (nur Editor)                   conditions[]}           (eingebettet)
  createdBy, createdAt,          task {taskId, releaseId,
  updatedAt                        beforeSurveyId, afterSurveyId,
                                   challenge}                     (eingebettet, kind=task)
                                 survey {surveyId, required}      (eingebettet, kind=survey)
                                 archivedAt | null, createdAt, updatedAt

learning_path_runs             learning_path_run_steps
  _id                            _id (= uuid5(runId, "step:" + stepId))
  learnerId                      runId, stepId (= Template-Step)
  templateId                     openedAt, completedAt
  createdAt                      modelId, workSubmittedAt          (nur Task)
  firstFinishedAt | null         challengeStartedAt, challengeStoppedAt
                                 surveySessionId | beforeSurvey | afterSurvey  (Session-IDs)
```

Regeln:

- **Reihenfolge** = Reihenfolge von `template.stepIds`. Einfügen/Umsortieren ändert nur dieses Array.
- **Indizes:** `(runId, stepId)` unique; `templateId` auf Template-Steps;
  `modelId` auf Run-Steps (ersetzt `stepStates.modelId` und den `$lookup` in `list_models`).
- `survey_sessions` bleibt unverändert; der Run-Step verweist auf die Session.
- Run-Step wird erst beim ersten Öffnen/Starten angelegt. "Gesperrt/Verfügbar" wird abgeleitet.
- `completedAt` eines Survey-Steps wird beim Einreichen/Überspringen der Session in den Run-Step
  geschrieben (kein Ableiten mehr aus der Session).
- Deterministische IDs (Run-Step, Modell, Session) bleiben, damit paralleles Anlegen idempotent ist.

## 3. Gewünschtes Verhalten

### Template-Steps

- Steps werden **nie gelöscht**, nur archiviert (`archivedAt`); Wiederherstellen ist möglich.
  `retiredStepIds` entfällt.
- **Unveränderlich:** `kind`, `taskId`, `surveyId` (Aktivität). Anderer Task oder Fragebogen =
  neuer Step, alter wird archiviert.
- **Veränderlich:** `title`, `unlock`, `releaseId`, `beforeSurveyId`, `afterSurveyId`, `challenge`,
  `required`. Wirkung auf bestehende Runs:
  - nicht gestartete Steps: sofort gültig;
  - gestartete Steps: `challenge`, `beforeSurveyId` und `afterSurveyId` werden immer aus dem
    Template gelesen (kein Snapshot; eine Änderung im selben Moment ist akzeptiert);
    `releaseId` und Modell bleiben an der gestarteten
    Version; Entwurfs-Sessions wechseln wie
    bisher auf das aktuelle Fragebogen-Release.
- Neue Steps dürfen an jeder Position eingefügt werden (auch in veröffentlichten Templates) und sind
  für alle bestehenden Runs sofort sichtbar.

### Sichtbarkeit und Freischaltung im Run

- **Sichtbar** ist ein Step, wenn er nicht archiviert ist **oder** ein Run-Step dazu existiert.
  Ein begonnener Step kann nie ausgeblendet werden. Details eines archivierten Steps sind nur über
  den eigenen Run-Step erreichbar.
- **Zugänglich:** Ein Run-Step mit `openedAt` bleibt immer bearbeitbar, auch wenn Voraussetzungen
  nachträglich hinzukamen. Alle anderen Steps benötigen erfüllte Voraussetzungen.
- **Unlock-Modi:**
  - `sequence` (Standard und aktuell einzige Regel in Seeds und Editor): alle vorherigen,
    nicht archivierten, nicht optionalen Steps in Array-Reihenfolge sind abgeschlossen.
  - `all` / `any`: explizite Bedingungen (`completed`, `after`, `at`) bleiben als Erweiterung in
    der API erhalten ("Custom rules" im Editor). Eine leere Liste bedeutet "immer frei".
  - `score` ist gesperrt (Scoring nicht angebunden): wird beim Speichern abgelehnt, bis ein
    vertrauenswürdiger Score-Adapter existiert.
- Beispiel: Neuer Step an Position 2, Lernende arbeitet an Step 7: Step 7 bleibt bearbeitbar, Step 8
  (`sequence`) bleibt gesperrt, bis der neue Step 2 abgeschlossen ist.
- **Archivierte Steps blockieren nie:** Sie werden bei `sequence` übersprungen. Bedingungen auf
  archivierte, nicht abgeschlossene Steps gelten als erfüllt; bereits abgeschlossene zählen weiter.
  Beim Speichern werden Bedingungen auf archivierte Steps abgelehnt.
- Wiederherstellen eines Steps wirkt wie Einfügen: er blockiert unbegonnene Folge-Steps wieder.
- Vor-/Nach-Fragebogen bleiben Teil des Task-Steps: Der Vor-Fragebogen gate't die Modellierung und
  startet die Challenge, der Nach-Fragebogen gate't den Abschluss.
- Fragebogen-Steps mit `required=false` sind überspringbar (Status `skipped`), dürfen keine
  Voraussetzung sein und werden bei `sequence` ignoriert.

### Fortschritt

- `total` = sichtbare, nicht archivierte Steps. Optionale Fragebogen-Steps zählen als erledigt,
  wenn sie abgeschlossen oder übersprungen sind. Archivierte, begonnene Steps
  zählen nie zu `total`/`finished`, auch wenn sie sichtbar bleiben und abschließbar sind.
- `progress`/`finished` werden bei jedem Abruf berechnet. `finished` kann wieder `false` werden,
  wenn ein neuer Step hinzukommt. `firstFinishedAt` am Run hält den ersten Abschluss fest
  (Statistik/Nachweis).
- Neu hinzugekommene Steps werden im UI über `createdAt` markiert (optional).

### Template-Lebenszyklus und Speichern

- `draft`: nicht startbar. `published`: startbar. `archived`: nicht neu startbar, bestehende Runs
  bleiben nutzbar.
- Änderungen an veröffentlichten Templates wirken sofort und live für alle Lernenden.
- `revision` am Template dient nur der Konfliktvermeidung zwischen Editoren; Lernende werden
  dadurch nie blockiert (`require_current_template` entfällt). Steps werden nur über das Speichern
  des Templates geändert; der Editor sendet weiterhin die aktive Step-Liste, fehlende Steps werden
  archiviert, erneut gesendete archivierte Steps wiederhergestellt.
- **Schreibreihenfolge:** zuerst Template-Revision-Guard (inkl. `stepIds`), dann die Step-Dokumente.
  So schreibt ein veralteter Editor keine Steps. Beim Lesen werden IDs in `stepIds` ohne
  Step-Dokument ignoriert.
- **Validierung:** `stepIds` eindeutig und nur Steps mit passender `templateId`; Zyklenprüfung
  inklusive der impliziten Kanten von `sequence`; nur existierende Referenzen; unveränderliche
  Felder unverändert; kein `score`; keine Bedingung auf archivierte Steps; bei `published` nur
  veröffentlichte Tasks und mindestens ein aktiver Step.

### Löschen und Integrität

- Modelle mit Run-Step-Bezug dürfen nicht hart gelöscht werden (Prüfung über Index `modelId`).
- Template-Steps werden nie physisch gelöscht.

## 4. Seed-Daten (`db/initial_data.py`)

Keine Migration; die DB wird neu initialisiert. Die Seeds müssen der neuen Struktur entsprechen:

- Für beide Beispielpfade (Order Management, Survey-Beispiel) je Step ein Dokument in
  `learning_path_template_steps` (`$setOnInsert`, `_id` deterministisch wie bisher) und im Template
  `stepIds` in der gewünschten Reihenfolge; `retiredStepIds` entfällt.
- Die bisherige Kette "completed des vorherigen Steps" wird zu `unlock: {mode: "sequence",
  conditions: []}`.
- Task-Steps tragen `task {taskId, releaseId, beforeSurveyId, afterSurveyId, challenge}`,
  Survey-Steps `survey {surveyId, required}`.
- Seeds erzeugen weiterhin keine Runs, Run-Steps, Sessions oder Modelle.
- `db/client.py`: neue Indizes anlegen, `stepStates.modelId`-Index entfällt.
- Anzupassen sind außerdem `template_fields`/`template_view`/`step_view` (Aufteilen in Template- und
  Step-Dokumente) und die Zugriffe in `learning_paths.py`, `learning_path_store.py` und `models.py`
  (`list_models`, `delete_model`, `ensure_task_questionnaire_completed`). Die API-Endpunkte bleiben
  gleich.
