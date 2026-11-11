# Umsetzungsprompt – Vergleichsgraph auf den Modeling-Layer begrenzen

**Stand:** Die Layer-Abgrenzung und die anschließenden Vereinfachungen der Schritte 02–04 sind implementiert und ausschließlich statisch durchgesehen. Der folgende Prompt dient einer gezielten Nachkontrolle beziehungsweise Korrektur dieses Stands. Die aktuellen Verträge in [Paket 02](02-graph-parser.md), [Paket 03](03-model-label-extraction.md), [Paket 04](04-synonym-matching.md) und der [Übersicht](README.md) bleiben dabei erhalten. Historische Evaluationsläufe belegen diese Änderungen nicht.

```text
Arbeite im Repository Modeling Copilot. Beachte AGENTS.md und den Skill
.agents/skills/modeling-copilot-workflow/SKILL.md. Antworte auf Deutsch;
Code, Bezeichner und Kommentare auf Englisch. Bewahre bestehende Nutzeränderungen.

Prüfe die bereits implementierte Abgrenzung des Vergleichsgraphen auf den
Modeling-Layer und korrigiere ausschließlich konkrete Abweichungen davon.
Bewahre die inzwischen umgesetzten kompakten Verträge der Schritte 02–04.
Keine neue Planung der gesamten Pipeline.

Lies zuerst:
- docs/model-comparison-work-packages/02-graph-parser.md, insbesondere
  „Nachfolgende Präzisierung: Vergleichsbereich Modeling-Layer“ und die offenen Kriterien.
- Die gemeinsamen Verträge in docs/model-comparison-work-packages/README.md.
- Die betroffenen Graphregeln in docs/model-comparison-pipeline-concept.md.
- dagu/workflow-services/graph-parser/src/parser.py und dessen direkten Aufrufer.
- Die Layer-Erstellung und -Zuordnung in
  web/src/components/modeling/canvas/DrawingCanvas.vue.
- Die direkten Graphverbraucher nur soweit für diese Abgrenzung erforderlich.

Ziel:
Der Vergleichsgraph enthält ausschließlich den rekursiven fachlichen Inhalt des
definierten Modeling-Layers. Bewahre die ausdrückliche Bereichsauswahl;
keinen Rückfall auf sämtliche nicht ausdrücklich ausgeschlossenen Zellen einführen.

Verbindliche Regeln:
1. Verwende die vorhandene Plattformkonvention zur Bestimmung des Modeling-Layers.
   Im aktuellen Editor ist der erste direkte Kindknoten der Canvas-Wurzel der
   Modeling-Layer, der zweite der Feedback-Layer. Prüfe diese Zuordnung anhand
   des bestehenden Exports. Keine festen Zell-IDs, Typnamen, Label-Heuristiken
   oder sprachspezifischen Ausnahmen einführen.
2. Canvas-Wurzel und beide Layer erzeugen weder Vergleichsknoten noch
   contains-Kanten. Oberste Modellbestandteile erhalten keinen künstlichen Besitzer.
3. Fachliche Container, verschachtelte Inhalte und deren unmittelbare
   Zugehörigkeiten innerhalb des Modeling-Layers bleiben erhalten. Unbekannte
   oder mehrdeutige Typen bleiben mit neutralen Diagnosen erhalten. Deklarierte
   Childs werden über die Parent-Definition aufgelöst; ungelöste Child-Kontexte
   erhalten UNRESOLVED_CHILD_DEFINITION. AMBIGUOUS_DEFINITION betrifft mehrere
   eigenständige Definitionen. Eigenständige Inhalte bleiben auch bei falscher
   Platzierung identifizierbar.
4. Feedback-Layer samt sämtlichen Nachfahren und sonstige Inhalte außerhalb des
   Modeling-Layers bleiben ausgeschlossen. Bereits ausdrücklich als Feedback
   gekennzeichnete Inhalte im Modeling-Layer bleiben ebenfalls ausgeschlossen.
5. Modellierte Verbindungen innerhalb des Vergleichsbereichs bleiben erhalten.
   Verbindungen zu nachweislich ausgeschlossenen Zellen und ihre zugehörigen
   Beschriftungen werden nicht übernommen. Tatsächlich fehlende Endpunktzellen
   weiterhin als offene Enden diagnostizieren; nicht mit Bereichsausschlüssen verwechseln.
6. Keine vollständigen XML-Einträge oder Einzeldiagnosen für regulär ausgeschlossene
   Infrastruktur und Inhalte außerhalb des Bereichs erzeugen. Ein kurzer Hinweis
   auf den verwendeten Vergleichsbereich genügt. graph.excluded bleibt als V1-Feld
   erhalten und darf leer sein; keine parallele Ausschlussliste einführen.
7. Reguläre Bereichsausschlüsse machen completeness.interpretation nicht partial.
   Sprachbeobachtungen beziehen sich ausschließlich auf übernommene Bestandteile.
8. Bei fehlender oder beschädigter Layerstruktur einen verständlichen technischen
   Eingabefehler liefern. Niemals still sämtliche übrigen Zellen als Modell verwenden.
   Ein vorhandener leerer Modeling-Layer ergibt einen gültigen leeren Graphen.
9. Wende dieselben Regeln auf alle Aufgaben, Abgaben und Musterlösungen an.
   comparisonConfig: {} bleibt ausreichend. Schema und Hüllen bleiben V1.
10. Elementinventar und Matching übernehmen die begrenzte Elementmenge aus dem
    Graphen. Bewahre graphPath/graphHash im kompakten Textinventar sowie
    inventoryPaths/inventoryHashes und Element-IDs im Kandidatenartefakt.
    Vorgängerergebnisse und deren Diagnosen nicht wieder einbetten. contains
    behält kind, source, target, directed, label, language und type, ohne zusätzliche
    ID, origin-Kopie oder leere properties; endpoint behält Anschlussdaten und Ports.
    Die Graphzusammenfassung unterscheidet Elemente, modellierte Verbindungen,
    Zugehörigkeiten und technische Anschlüsse. Kein zweiter XML-Parser.

Grenzen:
- Den vollständigen Eingabesnapshot und gespeicherte Modelle nicht verändern.
- Beschriftungsaufbereitung, Synonymmethoden und Gewichte nicht verändern;
  keine neuen Schwellenwerte oder Kürzung berechneter Kandidaten einführen.
  Die bereits umgesetzte Reduktion von Datenkopien durch Artefaktreferenzen bleibt erhalten.
- dagu/workflow-services/synonym-matching-louis/ bleibt vollständig unverändert.
- Keine neuen Architekturbausteine, Libraries, Konfigurationsparameter,
  Migrationspfade oder sprachspezifischen Sonderfälle.
- Keine neuen oder erweiterten Tests, Testdateien oder Test-Scaffolds.
- Für diesen begrenzten Auftrag nur statische Durchsicht der Änderungen und
  direkten Schnittstellen; keine Builds, Containerstarts, neuen Evaluationen,
  Testläufe, Lint- oder Syntaxprüfungen. Keinen Laufzeitnachweis behaupten.

Abschluss:
Setze nur tatsächlich erforderliche Korrekturen um und gleiche die betroffenen Dokumente
mit dem tatsächlichen Stand ab. Berichte knapp, wie der Layer bestimmt wird,
was im Graphen bleibt, was ausgeschlossen wird und welche offenen Grenzen bestehen.
Kennzeichne erfüllte Konzeptkriterien anhand der statischen Durchsicht;
unterscheide ausdrücklich zwischen Implementierung und Laufzeitverifikation.
```
