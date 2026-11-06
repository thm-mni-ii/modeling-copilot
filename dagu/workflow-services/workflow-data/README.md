# workflow-data (Init)

Prüft den vollständigen Snapshot und speichert ihn einmalig unter
`inputs/evaluation-input.json` im Laufordner. Der Dienst liest keine Datenbank
und erzeugt keine Parseraufträge, Indexdateien oder dienstspezifischen Eingaben.

## Austauschformat: minimales vollständiges Beispiel

Das Backend serialisiert dieses JSON als UTF-8, gzip-komprimiert und anschließend
Base64-kodiert nach `EVALUATION_INPUT_GZIP_BASE64`. `WORKFLOW_EVALUATION_ID` muss
mit `evaluationId` übereinstimmen.

```json
{
  "schemaVersion": 1,
  "schema": "evaluation-input/v1",
  "evaluationId": "example-run",
  "task": {
    "data": {
      "title": "Example task"
    },
    "workspaceLanguages": []
  },
  "models": [
    {
      "source": {
        "key": "submission",
        "role": "submission",
        "label": "Submission",
        "modelId": "model-1",
        "versionId": "version-1"
      },
      "snapshot": {
        "data": {
          "xml": "<GraphDataModel><root><Cell id=\"root\"/></root></GraphDataModel>"
        },
        "workspaceLanguages": []
      }
    }
  ],
  "languages": []
}
```

| Feld | Bedeutung |
| --- | --- |
| `task` | Vollständiger Aufgabensnapshot einschließlich benötigter Metadaten; das Beispiel ist bewusst minimal. |
| `models` | Genau eine `submission` und beliebig viele `reference`-Modelle mit eindeutigen Schlüsseln. |
| `models[].source` | Herkunft und festgelegte Modellversion; keine Aufforderung zum Nachladen. |
| `models[].snapshot` | Vollständige Modelldaten und verwendete Sprachversionen. |
| `languages` | Vollständige Definitionen aller benötigten Sprachversionen mit `languageId`, `versionId`, `data`, `includedLanguageVersions`. Siehe [Parserbeispiel](../graph-parser/README.md). |

Die JSON-Referenz dient dem Verständnis. `EvaluationInput` in `src/main.py`
unterstützt die IDE; die notwendigen Laufzeitprüfungen stehen ausdrücklich in
`prepare()`. Es wird kein JSON-Schema geladen.

## Ausgabe zum Beispiel

```json
{
  "schemaVersion": 1,
  "schema": "workflow-result/v1",
  "status": "ok",
  "mode": "data",
  "capability": "workflow-input",
  "summary": "1 vollständige Modell-Snapshots bereitgestellt",
  "result": {
    "evaluationId": "example-run",
    "inputSnapshot": "inputs/evaluation-input.json",
    "modelCount": 1
  }
}
```

Die Pfade sind relativ zum Laufordner. Nachfolgende Dienste lesen den Snapshot
mit `workspace().snapshot()`, unabhängig von einer bestimmten Pipeline.
Siehe [Datenfluss einer Auswertung](../../README.md#datenfluss-einer-auswertung).
