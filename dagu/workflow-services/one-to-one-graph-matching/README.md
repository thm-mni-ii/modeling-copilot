# one-to-one-graph-matching

Der Dienst liest über `WORKFLOW_EVALUATION_ID` und `REFERENCE_KEY` die Graphen,
Inventare und semantischen Kandidaten eines Modellpaares aus dem Workspace.
Er validiert Herkunft und Hashes und liefert `reference-comparison/v1` innerhalb
von `workflow-result/v1`. `comparisonHash` ist der kanonische SHA-256-Hash des
gesamten Ergebnisses ohne das eigene Hashfeld; `producer.resourceHash` erfasst
den verwendeten Servicecode und `workflow_io.py`.

`mapping.provisionalElements` enthält nur vorläufige Vorschläge. Die Kennzahlen
`anchorCoverage` und `capacityUpperBound` beziehen sich auf fachliche
`modelElement`-Knoten und sind **keine bestätigte Modellübereinstimmung**.
Die Obergrenze verwendet alle zulässigen Kandidaten, unabhängig von Ankern.
Leere Referenzmengen ergeben `null`. Die Verträglichkeit der Anker mit der
globalen Kapazität steht unter `proposalFeasibility`.

Optionale Mindestähnlichkeiten werden im eingefrorenen `comparisonConfig` als
`graphMatching.minimumSimilarity` angegeben: ein Objekt mit Methodennamen und
Mindestwerten. Nur deklarierte Methoden und Werte innerhalb ihrer Scorebereiche
sind zulässig. Ohne konfigurierte Mindestwerte ist die semantische Verfeinerung
als `not_configured` gekennzeichnet und erzeugt keine Vorschläge.

`semanticRefinement` unterscheidet unterstützte, unterschwellige und nicht
auswertbare Kandidaten sowie zusätzliche Vorschläge, ungeklärte Referenzen und
Referenzen ohne ausreichend unterstützten Kandidaten. Fehlende Scores werden
nicht als Null interpretiert; die vollständigen Kandidaten bleiben erhalten.
Ein Vorschlag setzt eindeutige Evidenz auf beiden Seiten und globale
Kapazitätsverträglichkeit voraus. Bei Gleichstand, widersprüchlichen Rangfolgen
oder unbekannter Konkurrenz bleibt die Zuordnung offen. Die zusätzliche
`metrics.semanticProposalCoverage` zählt nur neu vorgeschlagene Referenzen;
die bisherigen Anker- und Kapazitätskennzahlen bleiben getrennt.
Enthaltene Elemente benötigen eine durch unabhängige exakte Besitzeranker
gestützte Zugehörigkeit; Wurzelelemente können ohne Besitzer verglichen werden.

`metrics.provisionalRecognition` zählt Anker und zusätzliche semantische
Vorschläge getrennt und gemeinsam, insgesamt sowie nach Referenztyp und
Vergleichsklasse. `allCategories` summiert zusätzlich die Verbindungsvorschläge,
ohne daraus einen Gesamtscore zu bilden. `mapping.provisionalConnections` enthält nur eindeutig
unterscheidbare Verbindungen mit kompatiblen Typen beziehungsweise Gruppen,
bekannter Richtung und bereits vorläufig zugeordneten Endpunkten. Parallele,
nicht unterscheidbare Verbindungen und offene Endpunkte bleiben ungeklärt.

Für die Feedbackkategorien kann `comparisonConfig.graphMatching.elementCategories`
eine Liste von Einträgen wie
`{"languageId":"language","versionId":"version","type":"element-type","category":"nodes"}`
enthalten. Zulässige Elementkategorien sind `nodes`, `attributes` und `other`;
ohne passenden Eintrag gilt `other`. Verbindungen werden anhand ihrer Graphart
als `connections` klassifiziert. Die Zuordnung gilt je Sprach-ID, Version und
konkretem Typ und ist keine sprachspezifische Voreinstellung.

`metrics.byReferenceType` und `metrics.byComparisonClass` sind alternative
Ansichten und dürfen nicht addiert werden. Sie unterscheiden Sprach-ID und
Sprachversion. Die Anzahl studentischer Elemente in der Typansicht bezieht sich
auf denselben konkreten Typ; die Kapazität kann dennoch Kandidaten anderer Typen
derselben Vergleichsgruppe nutzen.

`metrics.provisionalOwnerConsistency` bewertet ausschließlich vorläufig
zugeordnete Elementpaare anhand unabhängiger exakter Besitzeranker. Die
zugehörigen Eltern, Besitzer und vollständigen Containment-Pfade stehen unter
`provisionalOwnerEvidence`. Paare ohne Zugehörigkeit auf beiden Seiten sind
nicht anwendbar und zählen nicht zum Nenner. Eine einseitige Zugehörigkeit
oder widersprüchliche Besitzeranker gelten als vorläufig verletzt; ungeklärte
Besitzer bleiben offen. Das Intervall reicht von `satisfied / expected` bis
`(satisfied + unresolved) / expected`; bei leerem Nenner sind beide Werte `null`.
Diese Kennzahl bestätigt weder Zuordnungen noch strukturelle Korrektheit.

Die Ausgabe bleibt partiell: `completeness.matching` ist `provisional`,
`completeness.structuralComparison` ist `provisional_owner_and_connections` und
`assessmentAvailable` ist `false`. Es gibt keine bestätigten Identitäten,
vollständige Struktur- oder Verbindungsbewertung und keine Noten. Bei gesetztem `WORKFLOW_OUTPUT_PATH`
wird das Ergebnis im Workspace gespeichert.
