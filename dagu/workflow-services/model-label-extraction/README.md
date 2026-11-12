# model-label-extraction

Erzeugt aus genau einem Parserergebnis ein vollständiges Elementinventar für das
spätere Synonym-Matching. Alle Modelle verwenden denselben Ablauf anhand ihrer
Graphdaten. Kein XML-Lesen, keine erneute Definitionsauflösung, Typzuordnung,
Labelzerlegung, Übersetzung oder Matchingentscheidung.

## Eingabe und Aufruf

- Eingabe ist die erfolgreiche `workflow-result/v1`-Hülle mit
  `result.schema: graph-result/v3` und `result.graph.schemaVersion: 3` aus Paket 02.
  Benötigt werden `evaluationId`, vollständige `source`, `inputHash`, `graphHash`,
  `producer`, `languageResources`, `graph`, `completeness` und `diagnostics`.
- `graph` enthält `nodes`, `edges` und `languages`. Knoten- und
  Kanten-IDs müssen gemeinsam eindeutige, nicht leere Strings sein. Der V3-Vertrag
  verwendet `kind` für Knotenkategorien und `role` für Kantenrollen; `properties` und
  `definitionCandidates` sind optionale, nicht leere Felder. Der Graphhash wird nach
  dem tatsächlichen Parservertrag geprüft:
  SHA-256 über genau `source`, `languageResources`, `producer`, `graph`,
  `completeness` und `diagnostics`.
- Im Workflow: `WORKFLOW_EVALUATION_ID`,
  `WORKFLOW_INPUT_PATH=graphs/<modelKey>.json` und
  `WORKFLOW_OUTPUT_PATH=labels/<modelKey>.json`. Lauf, `inputHash` und vollständige
  Modellquelle müssen zum eingefrorenen Workspace-Snapshot passen. Die Dateinamen
  der angegebenen Workflow-Pfade müssen `<source.key>.json` lauten; andere
  Verzeichnispräfixe sind möglich. Publikation bleibt atomar und unveränderlich.
- Eigenständig wird dieselbe vollständige Parserhülle über stdin, `TEMPLATE_INPUT`
  oder `--input` gelesen; Ausgabe über stdout beziehungsweise `--output`.
  Ohne Workspace werden Hülle, Laufkennung, Quellmetadaten und Graphhash geprüft;
  ein Abgleich mit einem externen Eingabesnapshot findet dann nicht statt.
- Keine neuen Parameter: `comparisonConfig: {}` reicht weiterhin aus.

## Inventarmenge und Texte

`elements` enthält ausschließlich Knoten mit `kind: modelElement` und
`comparisonRole: semantic`. Strukturelle, Verbindungs-, Beschriftungs- und nicht
eindeutig klassifizierte Knoten werden nicht als freie Elemente ausgegeben.
Gleiche Labels bleiben getrennte Instanzen mit ihren unveränderten IDs.
Die Graphstruktur bleibt unverändert unter dem referenzierten `graphPath`.

Jeder Elementeintrag übernimmt Identität, konkreten Typ, Vergleichsgruppe und
Sprachreferenz vom Graph Parser; nur der Beschriftungstext wird aufbereitet:

| Feld | Vertrag |
| --- | --- |
| `id` | Unveränderte ID des Knotens im referenzierten Modellgraphen. |
| `type` | Unveränderter konkreter Modelltyp oder `null`. |
| `comparisonGroup` | Unveränderte Vergleichsgruppe oder `null`. |
| `language` | Unveränderte Sprachreferenz `{languageId, versionId}` oder `null`. |
| `matchText` | Text ohne ausschließlich die bekannten, attributfreien Editor-Tags `b`, `strong`, `i`, `em`, `u`, `br`, `div` (Groß-/Kleinschreibung unerheblich). `br` wird zum Zeilenumbruch, `div` trennt Textblöcke. Reine Blockgrenzen erzeugen keinen führenden oder abschließenden Umbruch; explizite `br` bleiben erhalten. |
| `labelStatus` | `present` bei nicht leerem Vergleichstext, `missing` bei fehlendem/`null`-Label oder nach Formatentfernung nur leerem beziehungsweise Whitespace-Text. Andere JSON-Werte bleiben im Graphen, erhalten hier `unsupported` und leeren `matchText`. |
| `textLanguage` | Nur eine ausdrücklich am Graphknoten vorhandene natürliche Sprachangabe (nicht leerer String), sonst `null`. Der aktuelle Parser liefert keine solche Angabe. Keine Erkennung oder Ableitung aus `language`. |

`connectionTexts` enthält für jeden Verbindungsknoten genau einen `self`-Eintrag,
auch bei leerem Label. Jeder `connectionLabel`-Knoten erzeugt zusätzlich einen
`additionalLabel`-Eintrag. Sein Eigentümer wird ausschließlich über eine eindeutige
`contains`-Kante vom Beschriftungsknoten zu einem Verbindungsknoten ermittelt.
Fehlt dieser Besitzer oder ist er mehrdeutig, bleibt der Eintrag mit
`ownerConnectionId: null` erhalten und erhält eine Diagnose. Verbindungsrichtung,
Endpunkte und Graphkanten werden nicht in die Textprojektion kopiert.

Beide Textlisten behalten leere Labels; nicht-textuelle Werte ergeben
`labelStatus: unsupported`, eine Diagnose und `interpretation: partial`, ohne
andere gültige Einträge abzubrechen. Graphdiagnosen und Interpretationsstatus werden
übernommen. Es gibt keine Übersetzung, Synonymerkennung oder Ähnlichkeitsberechnung.

Die Regeln entsprechen den zugelassenen Anzeigeformatierungen in
`web/src/utils/htmlLabels.ts`. Unbekannte Tags, Tags mit Attributen, fachliche
Klammern, Typzeichen, Negationen, Ziffern, Groß-/Kleinschreibung und vorhandener
Whitespace bleiben erhalten. XML-Zeichenkodierung ist bereits im Parser aufgelöst;
gespeicherte Entity-Zeichenfolgen wie `&amp;` zeigt der Editor wörtlich an und sie
werden deshalb hier nicht nochmals HTML-dekodiert. Keine NFC-, linguistische oder
sonstige Whitespace-Normalisierung. Eine Leerheitsprüfung verändert den Text nicht.

Die Modellierungssprache und ihre Definitionsbindung bleiben ausschließlich im
Graphen und sind unabhängig von der natürlichen Sprache `textLanguage`.
Knoten mit `comparisonRole: unsupported` werden nicht als `elements` aufgenommen.
Ein fehlendes Label allein macht die Interpretation nicht unvollständig.

## Ausgabe und Herkunft

Ausgabe ist `workflow-result/v1`, `schemaVersion: 1`, `status: ok`,
`capability: model-label-extraction`, `mode: extract`. Unter `result` stehen:

| Feld | Inhalt |
| --- | --- |
| `schema` | `element-inventory/v2` |
| `evaluationId`, `source`, `inputHash`, `graphHash` | Unveränderte Lauf-, Modell- und Eingabebindung des Parserergebnisses. |
| `graphPath` | Relativer Eingabepfad im Auswertungsbereich; im Workflow aus `WORKFLOW_INPUT_PATH`, eigenständig standardmäßig `graphs/<source.key>.json`. Beim eigenständigen Aufruf muss der Aufrufer den referenzierten Graphen für spätere Nachverfolgung separat aufbewahren. |
| `producer` | Service `model-label-extraction`, Serviceversion `0.1.0` und `resourceHash` über die tatsächlichen Quelldateien `main.py` und `workflow_io.py`. |
| `elements` | Nach ID sortierte Einträge mit `id`, `type`, `comparisonGroup`, `language`, `matchText`, `labelStatus` und `textLanguage`. |
| `connectionTexts` | Nach Verbindungs-ID, Art, Label-ID und ID sortierte eigene Verbindungstexte und zusätzliche Beschriftungen. |
| `completeness`, `diagnostics` | Interpretationsstatus und Graphdiagnosen werden übernommen. Textextraktionsdiagnosen werden ergänzt; nicht-textuelle Werte oder ungelöste Besitzer setzen die Interpretation auf `partial`. |
| `inventoryHash` | SHA-256 über das gesamte `result` vor Ergänzung dieses Hashfelds. |

Hashes sind wie beim Parser 64-stellige Hexstrings ohne Präfix. Kanonisches
UTF-8-JSON verwendet sortierte Objektschlüssel, keine zusätzlichen Leerzeichen und
keine ASCII-Escapes. Inventarelemente werden nach ID, Diagnosen nach Code,
Element-IDs und Inhaltshash geordnet. Fachlich geordnete Inhalte behalten ihre
Reihenfolge. Zeitstempel und Laufzeitmessungen werden nicht ergänzt.

Falsche Hüllen/Versionen, widersprüchliche Lauf-/Quell-/Hashbezüge, ungültige IDs
oder fehlende V3-Strukturmetadaten liefern Exitcode 1 und eine Meldung auf stderr;
es wird kein neues Erfolgsartefakt veröffentlicht. Ein leeres Inventar ist gültig.
`interpretation: partial` wird niemals zu `complete` aufgewertet.

## Prüfstand und Übergabe

Acht gezielte Tests für SERM-/UML-/ERM-Projektionen, Verbindungsbeschriftungen,
ungültige Besitzer, Textstatus, Determinismus und Hash-/Evaluation-Validierung
bestanden. Das neu gebaute Extractor-Image erzeugte `element-inventory/v2`; das
neue Synonym-Matching-Image akzeptierte diese Ausgabe gegen sein V2-Schema.

Paket 04 liest die beiden kompakten Inventare über den bestehenden Workspace.
Strukturelles Matching, Feedback und Bewertung bleiben Folgeaufgaben. Der aktuelle
kompakte Vertrag bleibt auf diese Schnittstelle beschränkt.
