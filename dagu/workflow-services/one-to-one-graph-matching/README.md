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
Sie ist eine eingeschränkte Bestandskennzahl: Auch bei 100 % können offene
Elemente oder besitzerabhängige Vorschläge Strukturabweichungen verdecken.

`metrics.provisionalContainment` und `provisionalContainmentEvidence` ergänzen
eine separate, referenzbezogene Prüfung aller unmittelbaren `contains`-Kanten,
einschließlich struktureller Zwischencontainer und nicht zugeordneter Knoten.
Jede Beziehung enthält Quell- und Ziel-ID, Rolle, zugehörige Abgabe-IDs und
Eltern, vollständige Pfade, Zuordnungsgrundlagen, Abhängigkeiten, Status und
Entscheidungsgrundlage. `referenceRelationCount` ist der vollständige Nenner;
`satisfied + violated + unresolved` entspricht diesem Wert. Das Intervall
reicht von `satisfied / referenceRelationCount` bis
`(satisfied + unresolved) / referenceRelationCount`; bei leerem Nenner sind
beide Grenzen `null`.

Nur unabhängige exakte Elementanker können eine Beziehung als erfüllt oder
verletzt belegen. Besitzerabhängige, semantisch gewählte oder fehlende
Elementzuordnungen sowie mehrdeutige oder zyklische Pfade bleiben offen.
Ein struktureller Container kann anhand seiner eindeutigen Sprachdefinition
und eines unabhängig zugeordneten übergeordneten Elements abgeleitet werden.
Die eigene Beziehung des Containers zu diesem übergeordneten Element bleibt
jedoch offen: Ihre Verwendung zur Herleitung wäre zirkuläre Evidenz. Dies gilt
auch bei verschachtelten Containern. Vergleichbar sind unmittelbare Eltern;
die gespeicherte Kantenrolle wird dokumentiert, aber nicht zusätzlich bewertet.
Auch `satisfied` ist ausdrücklich keine bestätigte Identität oder Korrektheit.

Reproduzierbarer lokaler Prüfstand mit den vorhandenen Modell-JSONs, Parser,
v13-Elementvergleichsgruppen und vollständiger synthetischer Kandidatenmatrix
aus den Parserlabels; ohne Synonymverfahren oder vollständigen Pipeline-Lauf:

| Modell | Bisher: erfüllt / geprüft | Neu: erfüllt / verletzt / offen | Neu: Intervall |
| --- | --- | --- | --- |
| Referenz | 38 / 38 | 7 / 0 / 41 von 48 | 14,6–100 % |
| M03 | 36 / 37 | 5 / 1 / 42 von 48 | 10,4–97,9 % |
| M05 | 36 / 36 | 7 / 0 / 41 von 48 | 14,6–100 % |
| M08 | 35 / 35 | 6 / 0 / 42 von 48 | 12,5–100 % |

Die Intervalle sind wegen ungeklärter oder abhängiger Zuordnungen bewusst
breit. Insbesondere weist M05 damit keine gesicherte perfekte Übereinstimmung
aus; der Test allein beweist jedoch nicht, welche offenen Instanzen identisch
sind. Die Zahlen sind keine Ergebnisse des früheren, nicht verfügbaren
Workflow-Exports.

`provisionalConnectionStructure` vergleicht Verbindungsrelationen anhand der
vorläufig zugeordneten Endpunkte, ohne Verbindungsidentitäten zu erzwingen.
`byEndpoints` gruppiert nach ungeordnetem Endpunktpaar und enthält pro Seite
die ursprünglichen Verbindungs-IDs, Endpunkte, Typen und Richtungen.
`referenceOnlyCount` und `studentOnlyCount` beschreiben den Mengenüberschuss
je Endpunktpaar. Ein veränderter Endpunkt erscheint damit als Überschuss auf
beiden Seiten; daraus folgt keine Identität der betroffenen Verbindungen.

Bei gleicher, positiver Anzahl vergleichen `directionStatus` und `typeStatus`
die jeweiligen Multimengen (`equal`, `different` oder `not_evaluated`).
Gerichtete Verbindungen berücksichtigen Quelle und Ziel, ungerichtete nicht.
Konkrete Verbindungstypen werden nur bei bekannter, gleicher Sprachversion
verglichen; Vergleichsgruppen ersetzen diesen Typvergleich nicht.
`configurationStatus` vergleicht zusätzlich die Kombinationen aus Richtung
und Typ, damit parallele Verbindungen nicht fälschlich als gleich erscheinen.
Bei ungleichen Anzahlen oder unbekannten Metadaten bleibt die jeweilige
Eigenschaft unausgewertet. Parallele Verbindungen werden nicht gepaart.

`completeness` bezieht sich nur auf die Endpunktzuordnung der vorhandenen
Verbindungen. Offene oder nicht vorläufig zugeordnete Endpunkte stehen in
`unresolvedReferenceConnectionIds` beziehungsweise
`unresolvedStudentConnectionIds` und setzen sie auf `partial`. Dann sind
auch die Mengenüberschüsse nur Beobachtungen über den auswertbaren Teil und
kein Nachweis fehlender oder zusätzlicher Verbindungen im Gesamtgraphen.
Sämtliche Aussagen hängen von vorläufigen Elementzuordnungen ab; unveränderte
Erkennungsquoten bleiben davon getrennt.

Die Ausgabe bleibt partiell: `completeness.matching` ist `provisional`,
`completeness.structuralComparison` ist `provisional_owner_and_connections` und
`assessmentAvailable` ist `false`. Es gibt keine bestätigten Identitäten,
vollständige Struktur- oder Verbindungsbewertung und keine Noten. Bei gesetztem `WORKFLOW_OUTPUT_PATH`
wird das Ergebnis im Workspace gespeichert.
