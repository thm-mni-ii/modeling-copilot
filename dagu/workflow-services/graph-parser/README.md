# graph-parser

Überführt maxGraph-XML mit versionierten Sprachdefinitionen in einen Graphen.
Keine fachliche Validierung oder Modellkorrektur.

## Aufruf

- Eigenständig: `input.model.xml` und aufgelöste `input.languages` als JSON über
  stdin, `TEMPLATE_INPUT` oder `--input`; Ausgabe auf stdout oder über `--output`.
- Im Workflow: `WORKFLOW_EVALUATION_ID` und `MODEL_KEY` (Standard `submission`)
  wählen den Modell-Snapshot samt Sprachversionen und Abhängigkeiten.
- `WORKFLOW_INPUT_PATH` / `WORKFLOW_OUTPUT_PATH`: relative JSON-Dateipfade im
  Laufordner. Nur `mode: demo` erzeugt einen Dummy-Graphen.

## Graphformat

Ausgabe: `workflow-result/v1` mit `result.graph.schemaVersion: 2` und optionaler
Modellquelle `result.source`. Kein `complete`-Flag und keine fachlichen Diagnosen.
Vertrag: `ParserRequest` / `ParserResult` in `src/main.py`, `Graph` in `src/parser.py`.

| Feld | Bedeutung |
| --- | --- |
| `nodes[].kind` | `element` oder eine als Knoten dargestellte `connection`. |
| `edges[].kind` | `connection`: modellierte Verbindung; `contains` / `endpoint`: strukturelle Kante mit `role: structural`. |
| `edges[].relation` | Bei `contains`: `component` für sprachlich vordefinierte `children` / `additionalLabels`, `content` für hineingelegte eigenständige Elemente, sonst `null`. |
| `definition` / `definitionCandidates` | Sprachversion und JSON-Pointer innerhalb von `data`; Auflösung im Elternkontext, bei Mehrdeutigkeit Kandidaten statt Auswahl. |
| `parentId` / `properties` | Ursprüngliche XML-Eltern-ID und zusätzliche `diagramAttributes`. |
| `directed` / `storedUndirected` | Aufgelöste Richtung (`null`, falls unbekannt) und ursprünglicher XML-Wert; gespeicherte Angaben haben Vorrang. |
| `endpoints.source` / `.target` | Ursprüngliche `cellId`, Anschluss-ID, Koordinaten, Versätze, freie Endposition und eindeutig auflösbare Namen, Gruppen und Rollen. `pointSource`: `language` oder `model`. |

Beispiel: `Entität -- contains/component --> Attributliste -- contains/content --> Attribut`.
Die Beziehungen werden aus der vorhandenen Sprachdefinition abgeleitet;
Sprachen und Modellknoten benötigen keine Structural-Rolle.

Verbindungen mit Kindern, Verbindungen als Anschluss oder innerhalb eines
Modellcontainers werden als Knoten erhalten. Ihre gerichteten `endpoint`-Kanten
tragen die ursprüngliche Verbindungs-ID als `originId`; die Modellrichtung steht
am Verbindungsknoten. Strukturelle Kanten zählen nicht als Modellverbindungen.

Unbekannte Typen, offene Enden und Elternzyklen bleiben erhalten. Fehlende
Anschlussknoten ergeben `source` / `target: null`; Original-IDs bleiben in
`endpoints`. Feedback-Inhalte und technische Root-/Layer-Knoten werden ausgefiltert.
Bei Typnamenskonflikten mit regulären Definitionen wird Feedback nur anhand
expliziter Markierungen ausgeschlossen.
