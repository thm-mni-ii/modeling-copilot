# 01 · Graph Parser

> **Ist-Dokumentation** · Stand: `dagu(6).zip`, 16.11.2026 · Service `graph-parser` · `graph-result/v1`  
> **Aufgabe:** Einen gespeicherten maxGraph-Modellsnapshot **neutral und verlustbewusst** in einen typisierten Vergleichsgraphen übertragen. **Keine Erkennung, kein Matching, keine fachliche Bewertung.**

## Ablauf auf einen Blick

```text
Evaluation-Snapshot + Sprachdefinitionen
  → XML und Canvas-Struktur prüfen
  → ausschließlich Modeling-Layer wählen
  → Element-/Verbindungsdefinitionen auflösen
  → Graphknoten + contains-/endpoint-Kanten bilden
  → Diagnosen, Vollständigkeit, Herkunft und Hash veröffentlichen
```

**Pro Ausführung:** genau ein Modell (`submission` oder ein Referenzschlüssel). Der übergeordnete Dagu-Workflow startet diesen Dienst separat für alle Modelle.

## Eingabe → Ausgabe

| Eingang | Herkunft / Bedeutung |
|---|---|
| `inputs/evaluation-input.json` | Unveränderlicher `evaluation-input/v1`-Snapshot einschließlich `inputHash`, Modellquelle, Sprachversionen und Konfiguration |
| `MODEL_KEY` | Auszuwählendes Modell; standardmäßig `submission` |
| Modellformat | `GraphDataModel/root/Cell`, `maxgraph-xml` oder `maxgraph-model`, Version 1 |

**Ausgabe:** `graphs/<modelKey>.json` und identische Erfolgsantwort auf `stdout` (`parser-result.json`). `workflow-result/v1 → result.schema = graph-result/v1`; `graph.nodes`, `graph.edges`, `completeness`, `diagnostics`, `graphHash`, `languageResources`, `producer`. Die Workspace-Publikation ist atomar und unveränderlich.

## Verbindliche Verarbeitungsregeln

| Regel | Wann? | Was passiert? |
|---|---|---|
| **GP-01 · Canvas-Grenze** | Bei jedem Import | Genau **eine** Canvas-Wurzel ohne Parent; deren **erstes** direktes Kind ist Modeling-, das **zweite** Feedback-Layer. Die Reihenfolge des gespeicherten XML entscheidet, **nicht** die Cell-ID. |
| **GP-02 · Vergleichsbereich** | Nach Canvas-Prüfung | Nur Nachfahren des Modeling-Layers gehören zum Modellgraphen. Die Layer selbst sind keine Graphknoten; weitere Layer und Feedback-Layer bleiben außen vor. |
| **GP-03 · Feedback-Ausschluss** | Auch innerhalb des Modeling-Layers | Als Feedback markierte Zellen bzw. eindeutig als Feedbacktyp erkannte Objekte samt Nachfahren werden ausgeschlossen; Verbindungen zu ausgeschlossenen Zellen einschließlich deren Beschriftungen ebenfalls. |
| **GP-04 · Identität** | Für jede übernommene Zelle | Original-Cell-ID bleibt `node.id`. Technische Endpunkt-IDs werden kollisionsfrei unter `@graph:` abgeleitet. IDs sind keine fachlichen Matchingbeweise. |
| **GP-05 · Definition** | Bei der Typauflösung | Konkreten Zell-`type` erhalten; Sprachdefinition nach Typ, optional gepinnter Sprach-/Versionsangabe und Parent-Kontext auflösen. Mehrdeutige/unbekannte Definitionen bleiben mit Diagnose im Graphen. |
| **GP-06 · Klassifikation** | Bei jeder übernommenen Zelle | `modelElement`: eigenständiges Fachobjekt; `structuralElement`: eindeutig deklarierte verschachtelte Child-Struktur; `connection`: modellierte Linie; `connectionLabel`: zugehörige Zusatzbeschriftung. Unauflösbare Fälle können `kind: null` haben. |
| **GP-07 · Vergleichsgruppe** | Bei eindeutiger Sprachdefinition | Aus `language.data.evaluation.comparisonGroups`, getrennt für `elementTypes` und `connectionTypes`. Bei genau einer Gruppe deren ID; bei keiner oder mehreren `comparisonGroup: null` (Mehrfachzuordnung mit Diagnose). Ungruppierte Typen bleiben konkret unterscheidbar. |
| **GP-08 · Vergleichsrolle** | Bei jeder Zelle | Semantisch aufgelöste Fachobjekte/Verbindungen werden `semantic`, verschachtelte Container `structural`; nicht auswertbare Fälle/Verbindungslabels `unsupported`. Eine deklarierte Rolle wird berücksichtigt, ersetzt aber nicht die Objektart. |
| **GP-09 · Zugehörigkeit** | Für jede erhaltene Parentbeziehung | `contains` zeigt **Kind → unmittelbaren Parent**; `role: content` bei eigenständiger Definition, `component` bei verschachtelten Kindern/Zusatzlabels, sonst `null`. Zwischencontainer werden nicht übersprungen. |
| **GP-10 · Verbindung** | Für jede modellierte Linie | **Ein eigener `connection`-Knoten** mit konkretem Typ und `directed`. Dazu **zwei** technische `endpoint`-Kanten mit `role: source/target`. Richtung stammt aus `connectionUndirected`, sonst aus eindeutiger Sprachdefinition, sonst ungeklärt. |
| **GP-11 · Beschriftung/Eigenschaften** | Beim Auslesen | Text bleibt wie gespeichert (inkl. mehrzeiliger Labels). Skalare `diagramAttributes` bleiben Strings. Kein Zerlegen freier Texte in Attribute; nur `fontStyle`-Bits für fett/kursiv/unterstrichen als Textformatierung. |
| **GP-12 · Diagnosen** | Bei unvollständiger Interpretation | Offene Endpunkte, ungültige Besitzer, Mehrdeutigkeiten, Zyklen, unbekannte Richtung usw. werden dokumentiert. Nicht-informative Warnungen setzen `completeness.interpretation: partial`. Keine stillen Reparaturen. |

### Graphbild (technische Darstellung)

```text
[Attribut/Kind] ──contains(role)──> [Parent oder Strukturcontainer]
[Quellobjekt] ──endpoint(source)──> [Verbindung]
[Verbindung] ──endpoint(target)──> [Zielobjekt]
[Zusatzlabel] ──contains(component)──> [Verbindung]
```

Der Graph beschreibt **beobachtete Modellstruktur**. Ein nicht auflösbarer Endpunkt bleibt `null` mit `OPEN_ENDPOINT` – er wird nicht erraten.

## Harte Fehler vs. offene Interpretation

- **Abbruch ohne Erfolgsartefakt:** ungültiges XML, DTD/Entity, doppelte IDs, falsches Format/Version, fehlende oder ungültige Canvas-/Layerstruktur, ungültiger Snapshot/Hash.
- **Graph bleibt erhalten, aber `partial`:** etwa unbekannte Definition, ungültige Parent-Referenz, offene Anschlüsse, ungeklärte Richtung oder Containment-Zyklus.
- **Sicherungsregel:** Der Parser darf weder Eltern ersetzen noch unbekannte Zellen wegen fehlender Semantik automatisch einem anderen Layer zuordnen.

## Änderungslandkarte

| Zu ändernde Regel | Maßgebliche Stelle |
|---|---|
| Canvas, Scope, Zellauflösung, Kanten, Diagnosen | `dagu/workflow-services/graph-parser/src/parser.py` · `parse_model()` |
| Sprachdefinitionen und Vergleichsgruppen | `parser.py` · `language_catalog()` |
| Snapshot/Hash und Veröffentlichung | `graph-parser/src/main.py`, `workflow_io.py` |
| Dagu-Ausführung | `dagu/workflows/model-evaluation-graph-matching.yaml` · `graph-parser-model` |
| Regressionen | `graph-parser/tests/test_parser.py` |

**Für Textänderungen an dieser Datei:** Erst gewünschte Regel `GP-xx` ändern, dann Parsercode und Testfall anpassen. Keine Identitäts-/Matchinglogik hier einführen.
