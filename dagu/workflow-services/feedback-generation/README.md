# feedback-generation

Der Dienst liest mit `WORKFLOW_EVALUATION_ID` und `REFERENCE_KEY` den
eingefrorenen Snapshot und das Vergleichsartefakt `comparisons/<referenceKey>.json`.
Er validiert Herkunft, Schema, Hash und Konsistenz der vorläufigen Zähler.
Er berechnet keine Zuordnungen und erzeugt je Referenz ein `feedback-report/v1`
innerhalb von `workflow-result/v1`. `WORKFLOW_OUTPUT_PATH` speichert es im
Workspace.

Die Kategorien `nodes`, `attributes`, `connections` und `other` werden aus den
vom Vergleich gelieferten Typzählern aggregiert. Die Konfiguration der
Elementkategorien ist im [Graph-Matcher](../one-to-one-graph-matching/README.md)
beschrieben. Jede Kategorie und jeder konkrete Typ enthält Referenz- und
Abgabeanzahl, getrennte Anker-, Semantik- und Verbindungsvorschläge, ihre
gemeinsame vorläufige Anzahl, einen Prozentwert und einen Auswertungsstatus.
Ohne Referenzelemente oder ohne auswertbare Referenzen ist der Prozentwert
`null`. Bei teilweise auswertbaren Kategorien bleibt der Nenner vollständig und
der Status partiell. Nicht klassifizierte Elemente stehen in `other`; dessen
Status ist partiell.

Semantische Schwellen, offene Elemente und Verbindungen bleiben nachvollziehbar.
Wenn vorhanden, wird `provisionalConnectionStructure` aus dem Vergleich
unverändert in den Feedbackbericht übernommen; seine Grenzen und Felder sind
im [Graph-Matcher](../one-to-one-graph-matching/README.md) beschrieben.
Die dort dokumentierte `provisionalContainment`-Auswertung wird bei neuen
Vergleichen mit Referenzzählern, Intervall und Einzelbeziehungen übernommen;
ihre Zähler werden gegen die Einzelstatus validiert. Ältere Vergleiche ohne
diese Erweiterung bleiben lesbar.
Wenn vorhanden, übernimmt `provisionalTypeComparison` die vorläufige
Typauswertung für Elemente und Verbindungen einschließlich Einzelpaaren,
Abhängigkeiten, offenen Referenzen und Prozentnenner. Zähler und Paarstatus
werden gegen die vorläufigen Zuordnungen validiert. Ein kompatibler konkreter
Typunterschied ist keine automatische Fehlermeldung; die fachliche Zulässigkeit
bestimmen die Sprachmetadaten. Ältere Vergleiche ohne diese Erweiterung bleiben
lesbar.
Die Quoten sind vorläufige Erkennungszahlen, keine bestätigte fachliche
Übereinstimmung. Eine vollständige Strukturprüfung, Gesamtbewertung und Note
stehen nicht zur Verfügung.

## Projektion aus analytischem Feedback

Im aktuellen Auswertungsworkflow erhält der Dienst zusätzlich
`ANALYSIS_INPUT_PATH`. Dieser verweist auf das konkret im selben Referenz-Unterlauf
veröffentlichte `analysis-feedback/v1`. Herkunft, Analysehash, adressierter Pfad,
Vergleichsidentität und interne Konsistenz werden geprüft. Der Bericht aggregiert
seine bisherigen fachlichen Felder aus dem ursprünglichen Vergleich und ergänzt
`analysisHash` und `analysisPath`. Seine Erkennungszahlen werden mit der Analyse
abgeglichen. Es findet keine erneute Zuordnungsentscheidung statt.

Ohne `ANALYSIS_INPUT_PATH` bleibt die direkte Aggregation eines bestehenden
Vergleichs verfügbar. Gespeicherte frühere Berichte bleiben lesbar.
Analyse und kompakte Projektion sind interne Schritte des Hauptworkflows.
Details: [Analytical Feedback](../analytical-feedback/README.md).
