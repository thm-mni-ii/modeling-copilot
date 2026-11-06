# feedback-generation (Demo)

Fasst ausdrücklich gewählte Ergebnisdateien zusammen. Keine fest eingebauten
Vorgängerdienste und keine fachliche Bewertung. Nur im Demo-Workflow verwendet.

## Eingabe mit Laufkontext

```json
{
  "input": {
    "matching": "demo/results/matching.json",
    "units": "demo/results/units.json"
  }
}
```

Die Namen unter `input` sind frei wählbar, die Werte ausschließlich relative
JSON-Dateipfade im über `WORKFLOW_EVALUATION_ID` gewählten Laufordner. Fehlende
Dateien führen zum Fehler. Der Dienst wählt keine Ergebnisse automatisch aus.

## Eigenständiges minimales Beispiel

Eingabe:

```json
{"input": {}}
```

Ausgabe ohne Laufkontext:

```json
{
  "schemaVersion": 1,
  "schema": "workflow-result/v1",
  "status": "ok",
  "mode": "demo",
  "capability": "feedback-generation",
  "summary": "Demo-Ergebnisse zusammengeführt; keine fachliche Bewertung",
  "result": {
    "status": "not_implemented",
    "assessmentAvailable": false,
    "services": {}
  }
}
```

Bei ausgewählten Dateien enthält `result.services` deren Inhalte unter den
übergebenen Namen. Mit Laufkontext kommen `evaluationId` und der relative Pfad
`inputSnapshot` hinzu. Es wird kein JSON-Schema geladen; die obigen Beispiele
sind die Entwicklerreferenz.

Siehe [Datenfluss einer Auswertung](../../README.md#datenfluss-einer-auswertung).
