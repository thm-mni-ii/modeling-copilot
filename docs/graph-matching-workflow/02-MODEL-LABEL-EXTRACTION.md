# 02 · Model Label Extraction

> **Ist-Dokumentation** · Stand: `dagu(6).zip`, 16.11.2026 · Service `model-label-extraction` · `element-inventory/v1`  
> **Aufgabe:** Aus **einem** validierten Graphen eine reine, sprachneutrale **Textprojektion** erstellen. **Kein erneutes Parsing der Modellsemantik, keine Zuordnung.**

## Ablauf auf einen Blick

```text
graph-result/v1
  → Quelle, GraphHash, Knoten-IDs und Kanten validieren
  → semantische Fachobjekte auswählen
  → sichtbare Beschriftungen in matchText projizieren
  → eigene Verbindungstexte + Zusatzlabels erfassen
  → Inventar mit Original-IDs, Textstatus und Hash veröffentlichen
```

## Eingabe → Ausgabe

| Eingang | Inhalt |
|---|---|
| `graphs/<modelKey>.json` | Erfolgshülle des Parsers mit `graph-result/v1`, `graphHash`, Sprach-/Modellquelle und Diagnosen |
| Snapshot | Bei Workspace-Ausführung Prüfung von `evaluationId`, `inputHash` und Modellquelle |

**Ausgabe:** `labels/<modelKey>.json` plus `stdout` (`labels-result.json`); `workflow-result/v1 → result.schema = element-inventory/v1` mit `elements[]`, `connectionTexts[]`, `graphHash`, `inventoryHash`, `completeness`, `diagnostics`.

## Welche Objekte landen wo?

| Graphobjekt | Inventar | Begründung |
|---|---|---|
| `modelElement` mit `comparisonRole: semantic` | `elements[]` | Eigenständig semantisch vergleichbares Fachobjekt |
| `structuralElement` | Nicht in `elements[]` | Struktur bleibt im Parsergraphen; keine freie Textidentität |
| `connection` | `connectionTexts[]`, `kind: self` | Verbindungstext wird getrennt von Fachobjekten bewertet |
| `connectionLabel` | `connectionTexts[]`, `kind: additionalLabel` | Eigenständige ID, Textslot (`connectionLabelId`) und Referenz auf Besitzerverbindung |
| Unbekannte/`unsupported` Objektart | Nicht als semantisches Element | Keine selbst erfundene Vergleichssemantik |

## Verbindliche Regeln

| Regel | Bedingung | Umsetzung |
|---|---|---|
| **LE-01 · Quelle** | Jeder Aufruf | Akzeptiert nur gültige `workflow-result/v1`-Hülle mit `graph-result/v1` und korrektem `graphHash`. Keine widersprüchlichen IDs oder Kanten. |
| **LE-02 · Original-ID** | Jede Textinstanz | `id` bleibt die Originalknoten-ID; auch wiederholte gleiche Texte bleiben **separate** Inventareinträge. |
| **LE-03 · Textprojektion** | Für `label`-Strings | Ausschließlich einfache attributfreie Format-Tags `b`, `strong`, `i`, `em`, `u`, `br`, `div` werden für die angezeigte Textform berücksichtigt. `br`/`div` werden als Zeilengrenzen behandelt. |
| **LE-04 · Keine semantische Normalisierung** | Bei Textumwandlung | Kein Lowercasing, keine Synonymsuche, keine Interpretation von Attributnamen, keine HTML-Entity-Decodierung. Solche Schritte gehören ggf. zum späteren Synonymdienst. |
| **LE-05 · Textstatus** | Nach Projektion | `present`: nichtleerer Text; `missing`: `null`, leer oder nur Whitespace; `unsupported`: kein unterstützter String. `unsupported` führt zu Diagnose und partieller Interpretation. |
| **LE-06 · Metadaten** | Fachobjekt | Konkret `type`, `comparisonGroup`, `language`, `matchText`, `labelStatus`, `textLanguage`. Natürliche Textsprache und Modellierungssprache werden getrennt geführt. |
| **LE-07 · Verbindungs-Slots** | Zusatzlabel | Der Parent muss über **genau eine** `contains`-Beziehung auf einen `connection`-Knoten zeigen. Andernfalls `ownerConnectionId: null`, Diagnose und `partial`. |
| **LE-08 · Vollständigkeit** | Jede Inventarausgabe | Ursprüngliche Parser-Diagnosen bleiben erhalten; neue Text-/Besitzerdiagnosen ergänzen sie. Inventarhash bindet den gesamten Inhalt. |
| **LE-09 · Determinismus** | Veröffentlichung | Elemente nach ID; Verbindungstexte nach Besitzer, Art, Slot und ID sortieren. Identische Veröffentlichungen dürfen wiederholt werden. |

## Mini-Beispiel

```text
Graph:
  Modellknoten „<b>Projekt</b>“ (ID 13)
  Verbindung 80, Zusatzlabel „1:n“ (ID 81, connectionLabelId=cardinality)

Inventar:
  elements:         [{id: "13", matchText: "Projekt", labelStatus: "present", …}]
  connectionTexts: [{id: "80", kind: "self", …},
                    {id: "81", kind: "additionalLabel",
                     ownerConnectionId: "80", connectionLabelId: "cardinality", …}]
```

Das ist eine **Textansicht** des Graphen, keine Aussage darüber, ob „Projekt“ in der Referenz erkannt wurde.

## Grenzen und Zuständigkeit

- Keine **Bewertung** von Textähnlichkeit, kein Threshold, keine 1:1-Zuordnung.
- Es werden keine aus Layout oder freien Labels abgeleiteten Attribute erfunden.
- Zusatzbeschriftungen werden als Textsätze übergeben, aber **nicht als eigenständige fachliche Erkennungsinstanzen** gezählt.

## Änderungslandkarte

| Bereich | Maßgebliche Stelle |
|---|---|
| Texterkennung / Tags / `labelStatus` | `dagu/workflow-services/model-label-extraction/src/main.py` · `label_text()` |
| Inventarauswahl, Verbindungslabels, Hash/Diagnosen | `main.py` · `run()` |
| Dagu-Ausführung | `dagu/workflows/model-evaluation-graph-matching.yaml` · `model-label-extraction-model` |
| Schnittstellentests | `dagu/workflow-services/model-label-extraction/tests/` |

**Änderungsregel:** Wenn künftig eine zusätzliche Textquelle benötigt wird, zuerst `LE-xx` und die Inventarsemantik festlegen; Parserstruktur und Matchingentscheidung bleiben unberührt.
