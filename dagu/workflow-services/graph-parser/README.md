# graph-parser

Normalisiert maxGraph-XML anhand festgelegter Sprachversionen. Die folgenden
JSON-Beispiele beschreiben das Austauschformat; sie sind keine geladenen
JSON-Schemata. IDE-Typen stehen als `ParserRequest` / `ParserResult` in
`src/main.py` sowie als `Graph` und `Diagnostic` in `src/parser.py`.

## Eingabe: vollständiges, eigenständig ausführbares Beispiel

```json
{
  "input": {
    "model": {
      "xml": "<GraphDataModel><root><Cell id=\"root\"/><Cell id=\"layer\" parent=\"root\"/><Cell id=\"n1\" parent=\"layer\" vertex=\"1\" diagramElementType=\"entity\" value=\"Customer\"/></root></GraphDataModel>"
    },
    "languages": [
      {
        "languageId": "example",
        "versionId": "v1",
        "data": {
          "elements": [
            {
              "type": "entity"
            }
          ],
          "connections": []
        },
        "includedLanguageVersions": []
      }
    ]
  }
}
```

| Feld | Bedeutung |
| --- | --- |
| `input.model.xml` | Vollständiger maxGraph-Export. |
| `input.languages` | Benötigte Sprachdefinitionen einschließlich eingebundener Versionen. |
| `source` | Optional: `key`, `role` (`submission`/`reference`), `label`, `modelId`, `versionId`. Wird im Ergebnis erhalten. |
| `mode` | Standard `parse`; nur `demo` erzeugt einen ausdrücklich gekennzeichneten Dummy-Graphen. |

Alternativ wählt `WORKFLOW_EVALUATION_ID` den initialisierten Laufkontext;
`MODEL_KEY` wählt daraus das Modell (Standard `submission`). Dadurch ist kein
separater Parserauftrag pro Modell nötig. Ein expliziter JSON-Request hat Vorrang.

## Ausgabe zum obigen Beispiel

```json
{
  "schemaVersion": 1,
  "schema": "workflow-result/v1",
  "status": "ok",
  "capability": "graph-parser",
  "mode": "parse",
  "summary": "Modell normalisiert: 1 Knoten, 0 Kanten",
  "result": {
    "graph": {
      "schemaVersion": 1,
      "languages": [
        {
          "languageId": "example",
          "versionId": "v1"
        }
      ],
      "complete": true,
      "nodes": [
        {
          "id": "n1",
          "kind": "element",
          "type": "entity",
          "label": "Customer",
          "language": {
            "languageId": "example",
            "versionId": "v1"
          },
          "properties": {}
        }
      ],
      "edges": []
    },
    "diagnostics": []
  }
}
```

| Feld | Bedeutung |
| --- | --- |
| `status: ok` | Der Parser ist technisch fertig; keine Aussage über die fachliche Qualität. |
| `result.graph.complete` | `false`, sobald Fehlerdiagnosen vorliegen; dann keine verlässliche Bewertung. |
| `nodes[].kind` | `element` oder `connection`, wenn eine Verbindung selbst als Knoten adressierbar sein muss. |
| `edges[].kind` | `connection` für Modellverbindungen, `contains` für Verschachtelung, `endpoint` für Anschlüsse eines Verbindungsknotens. |
| `edges[].source` / `target` | Knoten-IDs; bei ungültigen Anschlüssen `null` plus Diagnose. |
| `edges[].directed` | `true` gerichtet, `false` ungerichtet, `null` unbekannt. |
| `properties` | Fachliche Attribute; kein Rendering-Stil und keine Geometrie. |
| `diagnostics[]` | `severity`, `code`, `cellId`, `message`, `details`; keine automatische Modellkorrektur. |

JSON kommt über `TEMPLATE_INPUT`, stdin oder `--input`; die Ausgabe geht auf
stdout oder mit `--output` in eine ausdrücklich gewählte Datei.
Mit `WORKFLOW_OUTPUT_PATH=graphs/submission.json` wird dasselbe Ergebnis zusätzlich
im Laufordner gespeichert. Der Dienst kennt dabei keine Namen anderer Schritte.

Speicher und Ablauf: [Datenfluss einer Auswertung](../../README.md#datenfluss-einer-auswertung).
