# graph-parser

Überführt einen eingefrorenen maxGraph-Snapshot anhand seiner mitgelieferten
Sprachdefinitionen in einen V1-Vergleichsgraphen. Alle Sprachen verwenden denselben
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

Es werden keine neuen Konfigurationsparameter eingeführt. `comparisonConfig: {}`
reicht aus; vorhandene Einträge bleiben unverändert im Eingabesnapshot.
Sprachprofile, manuelle Typzuordnungen, bestimmte Ressourcenhashes und sprachspezifische
Textgrammatiken werden nicht zur Verarbeitung vorausgesetzt.

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

Jede eindeutige mitgelieferte Element- oder Verbindungsdefinition für übernommene Zellen wird verarbeitet.
`type` erhält ihren Typstring, `nativeType` die ursprüngliche Typangabe der Zelle.
Typstrings verschiedener Sprachen oder Versionen sind erst zusammen mit ihrem
Sprach- und Definitionsbezug identifizierbar. Ohne eindeutige Definition bleibt
`type: null`; die Originalangaben und alle Kandidaten bleiben erhalten.

Übernommene Kindzellen bleiben eigenständige Knoten. Freie Labels, auch mehrzeilige,
bleiben unverändert und werden nicht in vermeintliche Attribute zerlegt.
`diagramAttributes` werden als die im XML vorliegenden skalaren Strings übernommen;
fehlende Schlüssel, leere Strings, `?` und ausdrücklich gesetzte Werte bleiben
unterscheidbar. Es gibt keine Konvertierung anhand von Feldnamen oder vermuteter
Bedeutung. Typ, Label und Herkunftsmetadaten werden separat geführt.

`comparisonRole` ist bei eindeutig definierten Knoten standardmäßig `semantic`, bei
fehlender oder mehrdeutiger Definition `unsupported`. Eine ausdrücklich gespeicherte
Rolle `semantic` oder `structural` an der Zelle, in `diagramAttributes` oder in der
aufgelösten Definition wird übernommen. Die Zelle hat dabei Vorrang. Ungültige
explizite Rollen erzeugen eine Diagnose. Rendering, Typnamen und Containerposition
begründen keine strukturelle Rolle.

## V1-Vertrag und Herkunft

Ausgabe: `workflow-result/v1`, darunter `result.schema: graph-result/v1` und
`result.graph.schemaVersion: 1`. `result` enthält `evaluationId`, die vollständige
Modellquelle `source`, `inputHash`, `languageResources`, `producer`, `graphHash`,
`graph`, `completeness.interpretation` und `diagnostics`.

`languageResources` nennt die tatsächlich zum Modell mitgelieferten Versionen samt
SHA-256 ihrer vollständigen Definitionsdaten (`language.data`). Dies dokumentiert die
Herkunft; die Hashes schalten keine Definitionen frei. `graph.languages` enthält die
entsprechenden Sprachreferenzen einschließlich der aufgelösten Abhängigkeiten.
Die tatsächlich verwendeten Sprachen ergeben sich aus den Modellknoten.

`producer` nennt Service `graph-parser`, die bestehende Serviceversion `0.4.2` und
`resourceHash`: SHA-256 des kanonischen Objekts aus den tatsächlich ausgeführten
Quelldateien `main.py`, `parser.py` und `workflow_io.py`. Damit ist die allgemeine
Verarbeitung eindeutig an eine unveränderliche Ressource gebunden. Diese Metadaten
liegen außerhalb des fachlichen Graphen.

`graphHash` ist SHA-256 des kanonischen Objekts mit genau `source`, `languageResources`,
`producer`, `graph`, `completeness` und `diagnostics`. Das UTF-8-JSON verwendet sortierte
Objektschlüssel, keine zusätzlichen Leerzeichen und keine ASCII-Escapes. Mengen
(Knoten, Kanten, Ausschlüsse, Sprachreferenzen, Definitionskandidaten und Diagnosen)
werden stabil geordnet; fachlich geordnete Inhalte behalten ihre Reihenfolge.
Das eigene Hashfeld, Zeitstempel und Laufzeitmessungen sind nicht enthalten.
`inputHash` verweist auf den vollständigen Snapshot aus Paket 01.

| Inhalt | Verhalten |
| --- | --- |
| Knoten | `kind: element` oder `connection`, `type`, `nativeType`, unverändertes `label`, `properties`, `comparisonRole`, Sprachbindung und `origin`. |
| Modellierte Beziehungen | Genau ein Knoten mit Original-ID, Label, Eigenschaften, Herkunft und `directed: true/false/null`, unabhängig von Kindern, Einbettung oder weiteren Anschlüssen. |
| Anschlüsse | Zwei technische `endpoint`-Kanten: Quelle → Beziehungsknoten und Beziehungsknoten → Ziel, mit `type: source/target`. Fehlende Enden bleiben `null`; Originalziel, Anschluss-ID, Koordinaten und freie Endposition stehen in `origin.anchor`. |
| Ports | Nur ausdrücklich in der aufgelösten Sprachdefinition vorhandene Namen, Gruppen oder Rollen stehen unter `port`. Layout und nur im Modell gespeicherte Anschlussmetadaten bleiben Herkunft. |
| Zugehörigkeit | `contains` erhält die unmittelbare Elternstruktur innerhalb des Modeling-Layers. `type: content` für eigenständige Definitionen, `component` für deklarierte Kinder/Zusatzlabels, sonst `null`. Wurzel und Layer erzeugen keine Kanten; fachliche Zwischencontainer bleiben sichtbar. Es gibt kein zweites persistiertes Besitzerfeld. |
| Ausschlüsse | Das V1-Feld `graph.excluded` bleibt als leere Liste erhalten. Reguläre Bereichsausschlüsse erzeugen weder XML-Einzeleinträge noch Einzelwarnungen. Konflikte mit regulären Definitionen verhindern weiterhin rein typbasierte Feedbackausschlüsse innerhalb des Modeling-Layers. |
| Identität | Originalknoten behalten ihre IDs; `endpoint`-IDs kodieren Transformationsrolle und Quellidentität kollisionssicher unter `@graph:`. `contains` wird durch `kind`, `source`, `target` identifiziert und besitzt keine zusätzliche ID. Die Reihenfolge der direkten Wurzelkinder bestimmt den Vergleichsbereich. |
| Originalwerte | Knoten behalten `origin.cellIds`, XML-Attribute, Eigenschaften und Regelbezug. `endpoint` behält Herkunft und Anschlussdaten. Die aus Quelle, Ziel und allgemeiner Erzeugungsregel rekonstruierbare Herkunft wird bei `contains` nicht nochmals gespeichert. |

`contains` enthält genau `kind`, `source`, `target`, `directed`, `label`, `language`
und `type`; leere `properties` entfallen. Technische Kanten werden stabil nach
Art, Quelle, Ziel und Typ sortiert. Die Zusammenfassung zählt Elementknoten
(einschließlich verschachtelter Inhalte), modellierte Verbindungen, Zugehörigkeiten
und technische Anschlüsse separat; sie errät keine sprachspezifischen Attributrollen.

Gespeichertes `connectionUndirected` (`0/1/false/true`) hat Vorrang. Ohne diesen Wert
gilt die eindeutig aufgelöste Sprachdefinition (`undirected`, gemäß bestehendem
Sprachschema standardmäßig `false`). Ungültige oder nicht auflösbare Richtungen bleiben
`null` mit Diagnose. Eine unbekannte Richtung wird nicht als ungerichtet behandelt.
Darstellungsstil, Position, Farbe und Größe werden nicht in fachliche Eigenschaften übernommen.

## Sprachherkunft und Diagnosen

Jedes Element und jede modellierte Beziehung trägt `language`, `languageResolution`,
`definition` und `definitionCandidates`. Alle zum Modell mitgelieferten Definitionen
werden gleichberechtigt berücksichtigt. Eine ausdrückliche Originalreferenz
(`languageId` und `languageVersionId` an der Zelle oder in `diagramAttributes`) muss
auf eine mitgelieferte Version verweisen; sie erhält Herkunft auch bei unbekanntem Typ.
Farbe, Form, Label und die Sprache eines Endpunkts liefern keinen Herkunftsbeleg.

Der Parent-Kontext wird für deklarierte `children` und `additionalLabels` vor der
endgültigen Typ-/Sprachbindung ausgewertet, unabhängig von Zell-ID-Reihenfolgen.
Eine passende Kinddefinition hat Vorrang; andernfalls bleiben eigenständige
Definitionen auch in fachlichen Containern verfügbar. Fehlende oder mehrdeutige
Child-Kontexte erzeugen `UNRESOLVED_CHILD_DEFINITION`, behalten den Knoten als
`unsupported` und machen die Interpretation `partial`. `AMBIGUOUS_DEFINITION`
bezieht sich auf mehrere eigenständige Definitionen. Der aufgelöste Parent-Kontext
steht ergänzend unter `origin.contextDefinitionCandidates`. Eigenständige Inhalte
werden nicht durch eine vermutete fachliche Besitzerregel ausgeschlossen. Sind
auch nach dieser Auflösung mehrere Definitionen derselben Version möglich,
ist die Sprache weiterhin `resolved`, die Definition aber `null`. Bei mehreren
Sprachversionen ist die Herkunft `ambiguous`, ohne Beleg `unresolved`. Technische
Strukturkanten haben keine eigene Modellierungssprache.

Diagnosen enthalten `code`, `severity`, `scope`, `message`, vollständige `source`,
`elementIds` und bei Bedarf Definitionen oder Originalfeldreferenzen. Codes:
`INVALID_LANGUAGE_REFERENCE`, `AMBIGUOUS_LANGUAGE_ORIGIN`, `UNRESOLVED_LANGUAGE_ORIGIN`,
`AMBIGUOUS_DEFINITION`, `UNRESOLVED_DEFINITION`, `UNRESOLVED_CHILD_DEFINITION`, `INVALID_COMPARISON_ROLE`,
`UNRESOLVED_DIRECTION`, `OPEN_ENDPOINT`, `INVALID_OWNER`, `CONTAINMENT_CYCLE` und
`MULTIPLE_LANGUAGE_ORIGINS` sowie die einmalige Bereichsinformation `COMPARISON_SCOPE`.

Konkrete Interpretationslücken sind Warnungen und setzen `interpretation: partial`;
ein vollständig aufgelöstes leeres Modell ist `complete`. Zyklen bleiben mit ihren
Kanten erhalten. Freitext oder eine weitere bekannte Sprache begründen keine Warnung.
Die optionale Beobachtung `MULTIPLE_LANGUAGE_ORIGINS` wird nur für tatsächlich erkannte
unterschiedliche Sprach-IDs als `info` ausgegeben und ändert die Vollständigkeit nicht.
Versionen derselben Sprache zählen dabei nicht als mehrere Sprachen. Aufgabenabgleich,
Zulässigkeit der Sprachwahl und daraus abgeleitetes Feedback bleiben nachgelagerten Regeln vorbehalten.
Sprachbeobachtungen beziehen sich ausschließlich auf übernommene Knoten;
`graph.languages` dokumentiert weiterhin alle mitgelieferten Sprachreferenzen.
Reguläre Bereichsausschlüsse und `COMPARISON_SCOPE` setzen die Interpretation nicht
auf `partial`. Inventar und Matching verwenden den begrenzten Graphen ohne neue XML-Auswahl.

## Prüfstand

Der generische Stand einschließlich Modeling-Layer-Abgrenzung wurde ausschließlich
statisch anhand von Parser, direktem Aufrufer, Editor, Export und Verbrauchern durchgesehen.
Frühere Ausführungen während der Entwicklung bezogen sich auf einen inzwischen
entfernten sprachspezifischen Zwischenstand und belegen diese Fassung nicht.
Keine neuen Testdateien, Builds oder vollständigen Testsuiten. Eine Laufzeitprüfung
des generischen Standes ist gemäß der aktuellen gemeinsamen README nicht ausgeführt.
Auch für diese Abgrenzung wurden keine Laufzeit-, Test-, Build-, Lint- oder
Syntaxprüfungen ausgeführt. Die strukturelle Zuordnung setzt die gespeicherte
Plattformreihenfolge voraus; vertauschte, ansonsten gleich strukturierte Layer
können ohne zusätzliche Kennzeichnung nicht als solche erkannt werden.
