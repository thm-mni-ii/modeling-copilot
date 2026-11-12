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
Die Quoten sind vorläufige Erkennungszahlen, keine bestätigte fachliche
Übereinstimmung. Eine vollständige Strukturprüfung, Gesamtbewertung und Note
stehen nicht zur Verfügung.
