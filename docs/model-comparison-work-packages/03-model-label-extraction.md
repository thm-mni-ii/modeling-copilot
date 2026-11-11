# 03 – Vollständiges Elementinventar und Vergleichstexte bereitstellen

**Baustein:** Container `model-label-extraction`, interner Workflow `model-label-extraction-model`.

**Abhängigkeit:** [02 – Graph-Parser](02-graph-parser.md). Es gelten die [gemeinsamen Verträge](README.md).

**Stand:** Paket 03 ist umgesetzt und ausschließlich statisch durchgesehen. Der
[Servicevertrag](../../dagu/workflow-services/model-label-extraction/README.md)
beschreibt die tatsächliche V1-Ein-/Ausgabe. Es gibt keine neuen
Konfigurationsparameter und keinen Laufzeitnachweis.

## Arbeitsziel

Aus jedem Vergleichsgraphen entsteht genau ein Elementinventar. Das semantische Matching erhält damit dieselben fachlichen IDs wie das strukturelle Matching. Leere Labels, gleiche Namen und erst bei der Normalisierung entstandene Attribute bleiben korrekt zugeordnet.

## Ausgangslage und relevante Stelle

[model-label-extraction/main.py](../../dagu/workflow-services/model-label-extraction/src/main.py) erweitert die vorhandene Extraktion beschrifteter Elemente zum vollständigen Inventar der semantischen und nicht sicher interpretierten Graphknoten. Unbeschriftete Instanzen bleiben erhalten; Graphhash und Eingabebezug werden geprüft. Originallabel und sichtbarer Vergleichstext sind getrennt.

## Was kommt hinein?

| Eingang | Inhalt |
|---|---|
| `WORKFLOW_EVALUATION_ID` | Laufbezug |
| `WORKFLOW_INPUT_PATH` | `graphs/<modelKey>.json`: vollständige erfolgreiche Parserhülle aus Paket 02 mit `result.schema: graph-result/v1` und `graph.schemaVersion: 1` |
| Eingabesnapshot | Im Workspace Abgleich von Lauf, vollständiger Modellquelle und `inputHash`; keine Textkonfiguration erforderlich |
| `WORKFLOW_OUTPUT_PATH` | `labels/<modelKey>.json` |

Es wird kein XML erneut gelesen. IDs, Typen, Rollen und Elementmengen stammen ausschließlich aus dem Graphen.

Eigenständig wird dieselbe Parserhülle über stdin, `TEMPLATE_INPUT` oder `--input`
übergeben; Ausgabe über stdout oder `--output`. Ohne Workspace findet kein Abgleich
mit einem externen Snapshot statt. Die Hülle enthält unter `result` außerdem
`evaluationId`, `source`, `inputHash`, `graphHash`, `producer`, `languageResources`,
`completeness` und `diagnostics`. `graph` enthält auch `languages` und `excluded`.
Der Graphhash wird exakt nach dem korrigierten Parservertrag geprüft. Die Dateinamen
der angegebenen Workflow-Ein-/Ausgabepfade müssen zur `source.key` passen;
Verzeichnispräfixe sind frei. `comparisonConfig: {}` bleibt ausreichend.

## Was kommt heraus?

Eine `workflow-result/v1`-Hülle mit `capability: model-label-extraction` und:

| Feld in `result` | Inhalt |
|---|---|
| `schema` | `element-inventory/v1` |
| `evaluationId`, `source` | Lauf und unveränderte Modellquelle |
| `inputHash`, `graphHash` | Unveränderte Bindung an Eingabesnapshot und Graph |
| `graphPath` | Relativer Pfad zur Eingabe im Auswertungsbereich, im Workflow aus `WORKFLOW_INPUT_PATH`; eigenständig standardmäßig `graphs/<source.key>.json` |
| `producer` | Inventarerzeuger mit bestehender Serviceversion und Hash seiner tatsächlichen Quelldateien `main.py` und `workflow_io.py` |
| `inventoryHash` | Hash des Inventars und seiner Erzeugungsgrundlage |
| `elements` | Alle fachlichen und nicht sicher interpretierten Element-/Beziehungsinstanzen |
| `completeness.interpretation`, `diagnostics` | Status berücksichtigt den Graphen; Diagnosen enthalten ausschließlich eigene Textaufbereitungsprobleme |

Ein Inventareintrag enthält genau `id`, `matchText`, `labelStatus` und
`textLanguage`. Vollständige Knoten, Originallabels, Typen, Modellsprachbindung,
Sprachressourcen und Parserdiagnosen bleiben im über `graphPath` und `graphHash`
referenzierten Graphen. Der Aufrufer eines eigenständigen Durchlaufs bewahrt die
referenzierte Eingabe separat auf. `textLanguage` bezeichnet eine natürliche
Sprache wie `de`, keine Modellierungssprache. Nur eine ausdrückliche Angabe am
Graphknoten wird übernommen, andernfalls `null`. Der aktuelle Parser liefert keine
natürliche Sprachangabe; aus Aufgabe, Label oder Modellierungssprache wird nichts
abgeleitet. Dafür wird kein vorläufiger Konfigurationsparameter eingeführt.

Konzeptioneller Beispielausschnitt; Quellen-, Sprach- und Eigenschaftsfelder sind
gekürzt. Die symbolischen Hashwerte sind Platzhalter; reale Hashes sind
64-stellige Hexstrings ohne Präfix. Dieses Beispiel wird nicht ausgeführt:

```json
{
  "schema": "element-inventory/v1",
  "evaluationId": "evaluation-1",
  "graphHash": "sha256:student-graph",
  "graphPath": "graphs/submission.json",
  "inventoryHash": "sha256:student-inventory",
  "elements": [
    {
      "id": "s1",
      "matchText": "Mitarbeiter",
      "labelStatus": "present",
      "textLanguage": null
    },
    {
      "id": "s9",
      "matchText": "",
      "labelStatus": "missing",
      "textLanguage": null
    }
  ],
  "completeness": { "interpretation": "complete" },
  "diagnostics": []
}
```

## Umgesetzter Arbeitsumfang

1. **V1-Graphvertrag lesen.** Hülle, Modellquelle und `graph.schemaVersion: 1` prüfen. Bestehende Leser direkt auf diesen initialen Vertrag abstimmen; keine parallelen Altformat-Leser einführen. Der Graphhash ist Bestandteil der Übergabe.
2. **Vollständige fachliche Menge übernehmen.** Element- und Beziehungsknoten mit `comparisonRole: semantic` aufnehmen, auch wenn ihr Label fehlt. `unsupported`-Knoten ebenfalls aufnehmen und ihre Einschränkung erhalten. Rein strukturelle Knoten sowie `contains`-/`endpoint`-Kanten sind keine semantischen Labelkandidaten.
3. **Originaltext und Vergleichstext trennen.** `label` bleibt unverändert im referenzierten Graphen. `matchText` entfernt nur die attributfreien Editor-Tags `b`, `strong`, `i`, `em`, `u`, `br`, `div`, unabhängig von Groß-/Kleinschreibung. `br` erzeugt Zeilenumbrüche, `div` trennt Textblöcke ohne künstlichen führenden oder abschließenden Umbruch. Unbekannte Tags und Tags mit Attributen bleiben wie in der Editor-Anzeige Text. Fachliche Typzeichen, Negationen, Ziffern oder unbekannte spitze Klammern werden nicht pauschal gelöscht. XML-Textkodierung ist bereits im Parser aufgelöst. Gespeicherte Entity-Zeichenfolgen werden vom Editor wörtlich angezeigt und deshalb hier nicht erneut HTML-dekodiert. Keine sprachspezifische Labelgrammatik.
4. **Leere und nicht lesbare Texte unterscheiden.** `labelStatus` ist `present`, `missing` oder `unsupported`. Fehlende/`null`-Labels und nach Formatentfernung leere beziehungsweise reine Whitespace-Texte werden `missing`, ohne den Vergleichstext zu trimmen. Der Parser liefert regulär Strings; andere JSON-Werte bleiben im Graphen erhalten und ergeben hier leeren `matchText`, `unsupported`, Diagnose `UNSUPPORTED_LABEL_TEXT` und `interpretation: partial`. Ein fehlendes Label allein erzeugt keine Interpretationslücke. Eine unklare fachliche Definition sperrt ein lesbares Label nicht automatisch.
5. **Linguistische Verarbeitung dem Semantikschritt überlassen.** NFC-/Whitespace-Normalisierung folgt dem dort eingefrorenen Verfahren. Dieses Paket liefert den sichtbaren Text und seine Herkunft; es führt keine Übersetzung, Synonymentscheidung oder aggressive Kleinschreibung durch.
6. **Identitäten unverändert übernehmen und Herkunft referenzieren.** Gleiche Labels mit unterschiedlichen IDs bleiben verschiedene Einträge. Ein Textcache darf später Berechnung sparen, aber keine Instanzen zusammenfassen. IDs bleiben erhalten. Sprach-/Definitionszuordnungen und Herkunft werden nicht kopiert; das Inventar referenziert den Graphen und trifft hierzu keine neue fachliche Entscheidung.
7. **Ausgabe stabil halten.** Einträge nach ID und eigene Diagnosen nach Code, Element-IDs und Inhaltshash sortieren. `inventoryHash` umfasst das gesamte kompakte `result` ohne das eigene Hashfeld, einschließlich Graphpfad/-hash, Modell-/Snapshot-Bezug, Erzeuger, Textaufbereitung und Vollständigkeit. Wie beim Parser: SHA-256 als 64-stelliger Hexstring ohne Präfix über kanonisches UTF-8-JSON mit sortierten Schlüsseln, ohne zusätzliche Leerzeichen oder ASCII-Escapes. Keine Zeitstempel und keine Paarbildung.

## Fehlerverhalten

Falscher Lauf, falsche Modellquelle, abweichende Hashes, ungültige oder doppelte
Knoten-IDs, doppelte Kantenkombinationen und ein nicht unterstützter Graphvertrag verhindern das Inventar
(Exitcode 1, stderr, kein neues Erfolgsartefakt). Knoten-IDs werden weder erzeugt
noch umgeschrieben. Eine leere Elementmenge ist gültig. Ein Graph mit eingeschränkter
Interpretation bleibt eingeschränkt. Parserdiagnosen werden über Graphpfad und
Graphhash referenziert und nicht nochmals im Inventar gespeichert. Technische
Kanten werden über Art, Quelle, Ziel und Typ auf eindeutige Kombinationen geprüft;
eine zusätzliche Kanten-ID ist für diese Prüfung nicht erforderlich.

## Erfüllungskriterien

**Statisch durchgesehen:** Die Häkchen beschreiben den implementierten Vertrag,
keinen Laufzeitnachweis.

- [x] Jede Inventar-ID existiert genau einmal im zugehörigen Graphen.
- [x] Alle fachlichen Element- und Beziehungsinstanzen sind vorhanden, einschließlich unbeschrifteter und erzeugter Bestandteile.
- [x] Gleiche Namen bleiben getrennte Instanzen; technische Kanten und ausdrücklich strukturelle Knoten werden nicht zu Labelkandidaten.
- [x] `label` im Graphartefakt und `matchText` im Inventar unterscheiden Herkunft und Vergleichstext nachvollziehbar.
- [x] Graphpfad, Graphhash und Modellquelle verknüpfen die Artefakte; der Status erhält bestehende Einschränkungen, Diagnosen enthalten ausschließlich eigene Textprobleme.
- [x] Beide Inventare stellen Paket 04 denselben kompakten V1-Vertrag bereit, ohne erneutes XML-Lesen oder neue ID-Vergabe.

**Aktuelle Verifikation:** Ausschließlich statische Durchsicht der Änderungen und Schnittstellen. Keine Tests erstellen, erweitern oder ausführen; keine manuellen Modell-/Containerläufe, Builds, Benchmarks, Lint- oder Syntaxprüfungen. Die Kriterien beschreiben Sollverhalten und sind derzeit kein Auftrag zur Ausführung.

**Übergabe:** [04 – Synonym-Matching](04-synonym-matching.md) erhält jeweils das Abgabeinventar und genau ein Referenzinventar.

**Offen:** Laufzeitverifikation des kompakten Vertrags nach gesondertem Auftrag,
strukturelles Matching und Gesamtabschluss in 05/06 sowie deren Integration in
07/08. Paket 04 und die Workflow-/API-Anbindung bis Phase 4 sind implementiert;
semantische Kandidaten sind noch keine bestätigten Zuordnungen. Die natürliche
Sprache bleibt ohne ausdrückliche Angabe unbekannt. Bewertung und
Feedbackgenerierung sind nicht implementiert.
