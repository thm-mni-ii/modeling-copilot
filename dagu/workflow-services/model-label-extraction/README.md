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

`elements` enthält jeden Graphknoten außer `kind: structuralElement` mit
`comparisonRole: semantic` oder `unsupported`, auch mit leerem oder fehlendem
Label. Gleiche Labels bleiben getrennte Instanzen mit ihren unveränderten IDs.
Die ausdrücklich als `structural` gekennzeichneten Knoten bleiben Kontext im
Graphen. Technische `contains`-/`endpoint`-Kanten werden keine Labelkandidaten.
Separate `properties` erzeugen keine neuen Einträge.
Es gibt keine Filter nach Typ, Modellierungssprache, `allowLabelEdit` oder Inhalt.

Jeder Eintrag enthält ausschließlich die unveränderte Graph-ID und das eigene
Ergebnis der Textaufbereitung. Originalknoten, Labels, Typen, Eigenschaften,
Sprachbindung und Parserdiagnosen werden über `graphPath`/`graphHash` referenziert:

| Feld | Vertrag |
| --- | --- |
| `id` | Unveränderte ID des Knotens im referenzierten Modellgraphen. |
| `matchText` | Text ohne ausschließlich die bekannten, attributfreien Editor-Tags `b`, `strong`, `i`, `em`, `u`, `br`, `div` (Groß-/Kleinschreibung unerheblich). `br` wird zum Zeilenumbruch, `div` trennt Textblöcke. Reine Blockgrenzen erzeugen keinen führenden oder abschließenden Umbruch; explizite `br` bleiben erhalten. |
| `labelStatus` | `present` bei nicht leerem Vergleichstext, `missing` bei fehlendem/`null`-Label oder nach Formatentfernung nur leerem beziehungsweise Whitespace-Text. Andere JSON-Werte bleiben im Graphen, erhalten hier `unsupported` und leeren `matchText`. |
| `textLanguage` | Nur eine ausdrücklich am Graphknoten vorhandene natürliche Sprachangabe (nicht leerer String), sonst `null`. Der aktuelle Parser liefert keine solche Angabe. Keine Erkennung oder Ableitung aus `language`. |

Die Regeln entsprechen den zugelassenen Anzeigeformatierungen in
`web/src/utils/htmlLabels.ts`. Unbekannte Tags, Tags mit Attributen, fachliche
Klammern, Typzeichen, Negationen, Ziffern, Groß-/Kleinschreibung und vorhandener
Whitespace bleiben erhalten. XML-Zeichenkodierung ist bereits im Parser aufgelöst;
gespeicherte Entity-Zeichenfolgen wie `&amp;` zeigt der Editor wörtlich an und sie
werden deshalb hier nicht nochmals HTML-dekodiert. Keine NFC-, linguistische oder
sonstige Whitespace-Normalisierung. Eine Leerheitsprüfung verändert den Text nicht.

Die Modellierungssprache und ihre Definitionsbindung bleiben ausschließlich im
Graphen und sind unabhängig von der natürlichen Sprache `textLanguage`.
`comparisonRole: unsupported` bedeutet keine automatische Textsperre: Ein lesbares
Label kann `labelStatus: present` haben, während die Parserdiagnose erhalten bleibt.
Ein fehlendes Label allein macht die Interpretation nicht unvollständig.

## Ausgabe und Herkunft

Ausgabe ist `workflow-result/v1`, `schemaVersion: 1`, `status: ok`,
`capability: model-label-extraction`, `mode: extract`. Unter `result` stehen:

| Feld | Inhalt |
| --- | --- |
| `schema` | `element-inventory/v1` |
| `evaluationId`, `source`, `inputHash`, `graphHash` | Unveränderte Lauf-, Modell- und Eingabebindung des Parserergebnisses. |
| `graphPath` | Relativer Eingabepfad im Auswertungsbereich; im Workflow aus `WORKFLOW_INPUT_PATH`, eigenständig standardmäßig `graphs/<source.key>.json`. Beim eigenständigen Aufruf muss der Aufrufer den referenzierten Graphen für spätere Nachverfolgung separat aufbewahren. |
| `producer` | Service `model-label-extraction`, bestehende Serviceversion und `resourceHash` über die tatsächlichen Quelldateien `main.py` und `workflow_io.py`. |
| `elements` | Nach Graph-ID sortierte Einträge mit genau `id`, `matchText`, `labelStatus`, `textLanguage`. |
| `completeness`, `diagnostics` | Vollständigkeitsstatus berücksichtigt die Eingabe; nur eigene Textdiagnosen werden ausgegeben. Nicht textuelle Labels ergänzen `UNSUPPORTED_LABEL_TEXT` und setzen die Interpretation auf `partial`. Parserdiagnosen bleiben ausschließlich im referenzierten Graphartefakt. |
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

Die sechs vorhandenen Graph-Parser-Unit-Tests liefen erfolgreich, einschließlich
SERM-, UML- und ERM-Fixtures. Das Parser-Image erzeugte ein `graph-result/v3`, das
vom neu gebauten Elementinventar-Image erfolgreich verarbeitet wurde. Vollständige
Modellabgaben waren nicht Teil dieser Prüfung.

Paket 04 liest die beiden kompakten Inventare über den bestehenden Workspace.
Strukturelles Matching, Feedback und Bewertung bleiben Folgeaufgaben. Der aktuelle
kompakte Vertrag bleibt auf diese Schnittstelle beschränkt.
