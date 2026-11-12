# graph-parser

Überführt einen eingefrorenen maxGraph-Snapshot anhand seiner mitgelieferten
Sprachdefinitionen in einen Graph-V3-Vergleichsgraphen. Alle Sprachen verwenden denselben
Parserpfad. Der Parser beschreibt Struktur und Herkunft neutral und erzeugt keine
Bewertung oder Rückmeldung zur fachlichen Richtigkeit.

## Eingabe und Aufruf

- Im Workflow wählen `WORKFLOW_EVALUATION_ID` und `MODEL_KEY` (Standard `submission`)
  das Modell aus `inputs/evaluation-input.json`. Sprachversionen und Abhängigkeiten
  werden ausschließlich aus diesem Snapshot aufgelöst.
- `WORKFLOW_OUTPUT_PATH=graphs/<modelKey>.json` veröffentlicht das Ergebnis atomar
  und unveränderlich über die bestehende Workspace-Logik. Identische Wiederholungen
  sind erlaubt; abweichende Inhalte am selben Pfad führen zum Konflikt.
- Eigenständig lautet die Anfrage `{ "input": <vollständiger evaluation-input/v1-Snapshot
  einschließlich inputHash>, "modelKey": "submission" }`. Eingabe über stdin,
  `TEMPLATE_INPUT` oder `--input`, Ausgabe über stdout oder `--output`.
  Eingabehash und Modellversionsbezug werden auch hier geprüft.
- Workspace-Aufrufe verwenden ausschließlich ihren Snapshot und `MODEL_KEY`;
  eingebettete Ersatzeingaben und `modelKey` im Request werden abgewiesen.
- Nur eigenständig erzeugt `mode: demo` ein ausdrücklich benanntes synthetisches
  Beispiel mit unbekanntem Typ und `interpretation: partial`.
- Unterstützt: `GraphDataModel/root/Cell`, Modellformat `maxgraph-xml` oder
  `maxgraph-model`, jeweils Version 1. Ein vorhandener leerer Modeling-Layer ist gültig;
  ein leeres `root` oder eine fehlende Layerstruktur ist ein technischer Eingabefehler.
- XML-Fehler, doppelte Zell-IDs, fremde Exportformate, DTD/Entities und ungültige
  Eingabebezüge liefern Exitcode 1 und eine verständliche Fehlermeldung auf stderr.
  Dabei wird kein neues Erfolgsartefakt veröffentlicht.

## Konfiguration und allgemeine Verarbeitung

Es werden keine neuen Konfigurationsparameter eingeführt. `comparisonConfig` bleibt
unverändert im Eingabesnapshot. Vergleichsgruppen werden je Sprachversion aus
`language.data.evaluation.comparisonGroups` gelesen. Gruppen können getrennte
`elementTypes` und/oder `connectionTypes` deklarieren; die beiden Kategorien
werden unabhängig aufgelöst. Nicht gruppierte Modellinstanzen und Verbindungen
behalten ihren konkreten Typ als Vergleichsgrundlage; der Parser bildet keine Kandidatenpaare. Sprachprofile, manuelle Typzuordnungen,
bestimmte Ressourcenhashes und sprachspezifische Textgrammatiken werden nicht
vorausgesetzt.

Der Vergleichsbereich wird vor der fachlichen Definitionsauflösung anhand der
Plattformstruktur bestimmt: genau eine Canvas-Wurzel ohne `parent`, deren erster
direkter Kindknoten der Modeling-Layer und deren zweiter der Feedback-Layer ist.
Die Zuordnung folgt `DrawingCanvas.vue`; `modelPersistence.ts` und der vorhandene
maxGraph-Codec exportieren die Kinder in gespeicherter Reihenfolge mit ihren
Teilbäumen. Maßgeblich ist daher die Reihenfolge der direkten Wurzelkinder im XML,
keine Sortierung nach Zell-ID. Wurzel und beide Layer dürfen weder `vertex` noch
`edge` sein. Fehlende oder verletzte Struktur führt zum Eingabefehler ohne Fallback.

Nur Nachfahren des Modeling-Layers werden übernommen. Fachliche Container und
unbekannte Inhalte bleiben erhalten; oberste Modellbestandteile haben keinen
künstlichen Besitzer. Feedback und dessen Nachfahren, weitere Layer und sonstige
Inhalte außerhalb dieses Bereichs bleiben ausgeschlossen. Die bestehende explizite
Feedbackerkennung innerhalb des Modeling-Layers gilt weiter. Verbindungen zu
vorhandenen ausgeschlossenen Zellen und ihre Kindbeschriftungen werden ebenfalls
rekursiv ausgeschlossen. Tatsächlich fehlende Endpunktzellen bleiben dagegen als
`OPEN_ENDPOINT` diagnostizierbar. Der vollständige Eingabesnapshot bleibt unverändert.
Modelltypisierte Waisen mit fehlender Eltern-ID, deren Layerzugehörigkeit nicht mehr
ermittelt werden kann, bleiben als `INVALID_OWNER`-Diagnose erkennbar, werden aber
nicht willkürlich dem Modeling-Layer zugeordnet.

Jede eindeutige mitgelieferte Element- oder Verbindungsdefinition für übernommene Zellen wird verarbeitet.
`type` erhält den konkreten Typ aus der Zelle, auch wenn keine eindeutige
Sprachdefinition dazu auflösbar ist. `definition` verweist bei einer eindeutigen
Zuordnung auf die Definition; die Referenz enthält den Pfad innerhalb der
Sprachversion und, falls vorhanden, deren Definitions-ID. Mehrdeutige oder
unbekannte Typen bleiben als Knoten samt Diagnosen erhalten.

Übernommene Kindzellen bleiben eigenständige Knoten. Freie Labels, auch mehrzeilige,
bleiben unverändert und werden nicht in vermeintliche Attribute zerlegt.
`diagramAttributes` werden als die im XML vorliegenden skalaren Strings übernommen;
fehlende Schlüssel, leere Strings, `?` und ausdrücklich gesetzte Werte bleiben
unterscheidbar. Es gibt keine Konvertierung anhand von Feldnamen oder vermuteter
Bedeutung. Typ, Label und Herkunftsmetadaten werden separat geführt.

`kind` unterscheidet `modelElement`, `structuralElement`, `connection` und
`connectionLabel`. Nur eine eindeutige Zuordnung zu einer verschachtelten
`children`-Definition des aufgelösten Parent-Typs begründet `structuralElement`;
eigenständige Elemente bleiben `modelElement`. Bei mehrdeutigen Child-Definitionen
bleibt `kind` ungeklärt (`null`) und eine Diagnose erhalten. Eine vorhandene
`comparisonRole` bleibt ergänzende Kompatibilitätsinformation; sie ersetzt nicht
diese Klassifikation.

## Graph-V3-Vertrag und Herkunft

Ausgabe: `workflow-result/v1`, darunter `result.schema: graph-result/v3` und
`result.graph.schemaVersion: 3`. `result` enthält `evaluationId`, die vollständige
Modellquelle `source`, `inputHash`, `languageResources`, `producer`, `graphHash`,
`graph`, `completeness.interpretation` und `diagnostics`.

`languageResources` nennt die tatsächlich zum Modell mitgelieferten Versionen samt
SHA-256 ihrer vollständigen Definitionsdaten (`language.data`). Dies dokumentiert die
Herkunft; die Hashes schalten keine Definitionen frei. `graph.languages` enthält die
entsprechenden Sprachreferenzen einschließlich der aufgelösten Abhängigkeiten.
Die tatsächlich verwendeten Sprachen ergeben sich aus den Modellknoten.

`producer` nennt Service `graph-parser`, die aktuelle Serviceversion `0.1.0` und
`resourceHash`: SHA-256 des kanonischen Objekts aus den tatsächlich ausgeführten
Quelldateien `main.py`, `parser.py` und `workflow_io.py`. Damit ist die allgemeine
Verarbeitung eindeutig an eine unveränderliche Ressource gebunden. Diese Metadaten
liegen außerhalb des fachlichen Graphen.

`graphHash` ist SHA-256 des kanonischen Objekts mit genau `source`, `languageResources`,
`producer`, `graph`, `completeness` und `diagnostics`. Das UTF-8-JSON verwendet sortierte
Objektschlüssel, keine zusätzlichen Leerzeichen und keine ASCII-Escapes. Mengen
(Knoten, Kanten, Sprachreferenzen, Definitionskandidaten und Diagnosen)
werden stabil geordnet; fachlich geordnete Inhalte behalten ihre Reihenfolge.
Das eigene Hashfeld, Zeitstempel und Laufzeitmessungen sind nicht enthalten.
`inputHash` verweist auf den vollständigen Snapshot aus Paket 01.

| Inhalt | Verhalten |
| --- | --- |
| Knoten | `kind` trägt die Knotenkategorie; `type` den konkreten Zelltyp und `label` den gespeicherten Text einschließlich Leertext. `comparisonGroup` ist für eindeutig gruppierte Modellinstanzen oder Verbindungen gesetzt, andernfalls `null`. `properties` und `definitionCandidates` erscheinen nur bei nicht leeren Werten. |
| Modellierte Beziehungen | Genau ein `connection`-Knoten mit Original-ID, konkretem Verbindungstyp und eigener `directed`-Information. Keine zusätzliche, unabhängig gepflegte Verbindungsstruktur und keine abgeleitete fachliche Richtungsregel. |
| Anschlüsse | Zwei technische `endpoint`-Kanten mit `role: source/target` bewahren Rollen und Reihenfolge der Endpunkte. Fehlende Enden bleiben `null` und erzeugen `OPEN_ENDPOINT`. |
| Verbindungsbeschriftungen | Zellen mit `connectionLabelId` erhalten `kind: connectionLabel`, behalten Kennung und Text und bleiben über ihre gespeicherte `contains`-Beziehung der ursprünglichen Verbindung zugeordnet. |
| Zugehörigkeit | `contains` erhält jede unmittelbare Elternbeziehung innerhalb des Modeling-Layers in Richtung Kind → Parent. `role: content` für eigenständige Definitionen, `component` für deklarierte Kinder/Zusatzlabels, sonst `null`. Wurzel und Layer erzeugen keine Kanten; fachliche Zwischencontainer bleiben eigenständige Knoten. |
| Identität | Originalknoten behalten ihre IDs; `endpoint`-IDs kodieren Transformationsrolle und Quellidentität kollisionssicher unter `@graph:`. Eine Kante wird durch `kind`, `source`, `target` und `role` identifiziert. Die Reihenfolge der direkten Wurzelkinder bestimmt den Vergleichsbereich. |
| Eigenschaften | `contains` besteht aus `kind`, `source`, `target` und `role`; `endpoint` ergänzt die eigene `id`. Technische Kanten tragen keine redundanten Labels, Sprachen, Richtungs- oder Eigenschaftenfelder. Die fachliche Verbindungsrichtung liegt nur am Verbindungsknoten. |

Wenn ein gültiges maxGraph-`fontStyle`-Bitfeld gespeichert ist, enthält
`properties.textFormatting` dessen ursprünglichen Zahlenwert sowie die Flags
`bold`, `italic` und `underline` (maxGraph-Bits 1, 2 und 4). Andere visuelle
Style-Informationen werden nicht übernommen; die gespeicherte Beschriftung bleibt
unverändert. Der Parser leitet daraus keine fachliche Bedeutung ab.

Technische Kanten werden stabil nach Art, Quelle, Ziel und Rolle sortiert. Die Zusammenfassung zählt Elementknoten,
modellierte Verbindungen, Zugehörigkeiten und technische Anschlüsse separat.
`comparisonGroup` ist die Gruppen-ID aus der jeweiligen Sprachversion; ohne eindeutige
Gruppenzuordnung bleibt sie `null`. Für mehrfach konfigurierte Element- oder
Verbindungstypen wird `AMBIGUOUS_COMPARISON_GROUP` diagnostiziert. Strukturelle Elemente und Verbindungen werden
nicht allein über eine Vergleichsgruppe als semantische Modellinstanzen behandelt.
`graph-result/v3` verwendet `kind` für Knotenkategorien und `role` für Kantenrollen.
Die bisherige Reduktion bleibt bestehen; `graph.excluded` wird nicht ausgegeben.
Verbraucher müssen `contains` als Kind → Parent interpretieren. Ein bekannter Quelltyp
bleibt auch ohne aufgelöste Definition in `type` erhalten.

## Sprachherkunft und Diagnosen

Jedes Element und jede modellierte Beziehung trägt `language`, `languageResolution`
und `definition`. Nicht leere `definitionCandidates` werden zusätzlich ausgegeben.
Alle zum Modell mitgelieferten Definitionen
werden gleichberechtigt berücksichtigt. Eine ausdrückliche Originalreferenz
(`languageId` und `languageVersionId` an der Zelle oder in `diagramAttributes`) muss
auf eine mitgelieferte Version verweisen; sie erhält Herkunft auch bei unbekanntem Typ.
Farbe, Form, Label und die Sprache eines Endpunkts liefern keinen Herkunftsbeleg.

Der Parent-Kontext wird für deklarierte `children` und `additionalLabels` vor der
endgültigen Typ-/Sprachbindung ausgewertet, unabhängig von Zell-ID-Reihenfolgen.
Eine eindeutige passende `children`-Definition begründet einen strukturellen Knoten;
andernfalls bleiben eigenständige Definitionen auch in fachlichen Containern
`modelElement`. Fehlende oder mehrdeutige Child-Kontexte erzeugen
`UNRESOLVED_CHILD_DEFINITION`, behalten den Knoten mit ungeklärtem `kind` und
machen die Interpretation `partial`. `AMBIGUOUS_DEFINITION` bezieht sich auf mehrere
eigenständige Definitionen. Nicht leere Definitionskandidaten stehen in der Diagnose.
Eigenständige Inhalte werden nicht durch eine vermutete
fachliche Besitzerregel ausgeschlossen. Sind
auch nach dieser Auflösung mehrere Definitionen derselben Version möglich,
ist die Sprache weiterhin `resolved`, die Definition aber `null`. Bei mehreren
Sprachversionen ist die Herkunft `ambiguous`, ohne Beleg `unresolved`. Technische
Strukturkanten haben keine eigene Modellierungssprache.

Diagnosen enthalten `code`, `severity`, `scope`, `message`, vollständige `source`,
`elementIds` und bei Bedarf Definitionen oder Originalfeldreferenzen. Codes:
`INVALID_LANGUAGE_REFERENCE`, `AMBIGUOUS_LANGUAGE_ORIGIN`, `UNRESOLVED_LANGUAGE_ORIGIN`,
`AMBIGUOUS_DEFINITION`, `UNRESOLVED_DEFINITION`, `UNRESOLVED_CHILD_DEFINITION`,
`INVALID_COMPARISON_ROLE`, `AMBIGUOUS_COMPARISON_GROUP`, `OPEN_ENDPOINT`,
`INVALID_CONNECTION_LABEL_OWNER`, `INVALID_OWNER`, `CONTAINMENT_CYCLE` und
`MULTIPLE_LANGUAGE_ORIGINS`.

Konkrete Interpretationslücken sind Warnungen und setzen `interpretation: partial`;
ein vollständig aufgelöstes leeres Modell ist `complete`. Zyklen bleiben mit ihren
Kanten erhalten. Freitext oder eine weitere bekannte Sprache begründen keine Warnung.
Die optionale Beobachtung `MULTIPLE_LANGUAGE_ORIGINS` wird nur für tatsächlich erkannte
unterschiedliche Sprach-IDs als `info` ausgegeben und ändert die Vollständigkeit nicht.
Versionen derselben Sprache zählen dabei nicht als mehrere Sprachen. Aufgabenabgleich,
Zulässigkeit der Sprachwahl und daraus abgeleitetes Feedback bleiben nachgelagerten Regeln vorbehalten.
Sprachbeobachtungen beziehen sich ausschließlich auf übernommene Knoten;
`graph.languages` dokumentiert weiterhin alle mitgelieferten Sprachreferenzen.
Reguläre Bereichsausschlüsse setzen die Interpretation nicht auf `partial`.
Inventar und Matching verwenden den begrenzten Graphen ohne neue XML-Auswahl.

## Prüfstand

Mit `PYTHONPATH=src python -m unittest discover -s tests` prüft der gezielte
Lauf SERM-Container und Attribute,
unterscheidbare strukturelle Child-Definitionen, UML-Freitextlabels, ERM-Verbindungen
und Zusatzlabels sowie unbekannte Typen, fehlende Referenzen und mehrdeutige
Child-Definitionen.
