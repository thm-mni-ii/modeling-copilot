# workflow-data

Prüft und speichert den Auswertungs-Snapshot unveränderlich unter
`inputs/evaluation-input.json` im Laufordner.

- Eingabe: `evaluation-input/v1` als UTF-8-JSON, gzip-komprimiert und Base64-kodiert
  über `EVALUATION_INPUT_GZIP_BASE64`.
- `WORKFLOW_EVALUATION_ID` muss mit `evaluationId` übereinstimmen.
- Der Snapshot enthält `task`, `models` mit `source` und `snapshot` sowie sämtliche
  referenzierten Sprachversionen unter `languages` einschließlich Abhängigkeiten.
- Ausgabe: `workflow-result/v1` mit `evaluationId`, `inputSnapshot` und `modelCount`
  unter `result`.

Vertrag und Eingangsprüfungen: `EvaluationInput` und `prepare()` in `src/main.py`.
Nachfolgende Dienste lesen den Snapshot über `workspace().snapshot()`.
