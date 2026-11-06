# synonym-matching (Demo)

Platzhalter für Synonymzuordnung; kein fachlicher Algorithmus und keine Bewertung.
Der reguläre Workflow endet beim Parser. Dieser Dienst bleibt für den
[Demo-Workflow](../../workflows/demo-model-evaluation.yaml) verfügbar.

## Austauschformat

Der Dienst liest eine Graphausgabe wie im vollständigen
[Parserbeispiel](../graph-parser/README.md#ausgabe-zum-obigen-beispiel), konkret
`result.graph`. Er benötigt keine bestimmte `capability` und kennt keinen
Vorgängerschritt. `WORKFLOW_INPUT_PATH` wählt eine konkrete Datei im Laufordner.
Fehlt ein Graph, wird der Aufruf abgelehnt. Ein eigenständiger Dummy-Aufruf ist
nur ausdrücklich als Demo möglich:

```json
{"mode": "demo"}
```

Ausgabe dazu ohne Laufkontext:

```json
{
  "schemaVersion": 1,
  "schema": "workflow-result/v1",
  "status": "ok",
  "mode": "demo",
  "capability": "synonym-matching",
  "summary": "Synonymzuordnung: Algorithmus noch nicht implementiert",
  "result": {
    "status": "not_implemented",
    "assessmentAvailable": false,
    "matches": []
  }
}
```

Bei einer Graphdatei kommen Knotenzahl und Kantenzahl unter `result.observed`
hinzu; unvollständige Graphen führen zu `result.status: blocked`. Optional
simuliert `demoDelaySeconds` (0–30) Laufzeit. `status: ok` bezeichnet nur die
technische Verarbeitung. `assessmentAvailable: false` bleibt immer gesetzt.

Dies ist eine lesbare Format-Referenz, kein geladenes JSON-Schema.
Speicher und Zugriff: [Datenfluss einer Auswertung](../../README.md#datenfluss-einer-auswertung).
