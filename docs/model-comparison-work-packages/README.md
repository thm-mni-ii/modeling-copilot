# Arbeitspakete für die Modellvergleichs-Pipeline

Die nachfolgende Vereinfachung der Schritte 02–04 ist implementiert und ausschließlich statisch durchgesehen: deklarierte Childs werden im Parent-Kontext aufgelöst, Zwischenartefakte referenzieren ihre Eingaben, die Graphzusammenfassung trennt Modellbestandteile und technische Kanten, und `contains` verwendet einen kompakten Vertrag. Ein Laufzeitnachweis für diese Änderungen liegt nicht vor.

## Arbeitsziel

Die vorhandenen Workflow-Services werden schrittweise zu einer ausführbaren One-to-One-Vergleichspipeline verbunden. Jedes Paket beschreibt einen abgegrenzten Auftrag mit Eingabe, Ausgabe, Verhalten und Erfüllungskriterien. Die Pakete sind Umsetzungsvorgaben; ihr jeweiliger Stand und die verlinkten Serviceverträge kennzeichnen bereits implementierte Schnittstellen.

Grundlage ist das [Gesamtkonzept](../model-comparison-pipeline-concept.md). Diese Arbeitsplanung konkretisiert dessen Übergänge. Fachlich noch abzustimmende Annahmen werden nicht als bereits beschlossene Regeln behandelt.

Das initiale Ergebnis enthält Zuordnungen, strukturelle Befunde, Mehrdeutigkeiten und technische Einschränkungen. Die Verarbeitung ist von Beginn an allgemein für alle Aufgaben, Abgaben und Sample Solutions im vorhandenen Modellformat vorgesehen. Maßgeblich sind ihre mitgelieferten Sprachdefinitionen; es gibt keine Beschränkung auf eine Pilotsprache. Automatische Noten, didaktische Feedbackgenerierung und MMU-Matching sind anschließende Erweiterungen.

**Verbindliche Korrektur des Arbeitsrahmens:** Keine sprachspezifischen Parserzweige, fest einprogrammierten Typzuordnungen, Referenzmodell-Hashes oder Textgrammatiken. Kein Pflichtprofil und keine manuelle Typ-Mappingliste je Sprache, Aufgabe oder Sample Solution. Auch eine bisher unbekannte, vollständig mitgelieferte Sprachdefinition muss durch denselben allgemeinen Ablauf verarbeitet werden können. Fehlende oder mehrdeutige Daten bleiben neutral markiert; sie rechtfertigen keine Spezialisierung auf eine einzelne Sprache.

**Derzeit keine Ausführung zur Verifikation:** Keine Tests erstellen, erweitern oder ausführen; auch keine manuellen Probe-/Containerläufe, Smoke-Tests, Benchmarks, Builds, Lint- oder Syntaxprüfungen. Die jetzt beauftragte Umsetzung und Korrektur erfolgt durch Lesen, Bearbeiten und statische Durchsicht der Änderungen. Spätere Laufzeitprüfungen benötigen einen gesonderten Auftrag und sollen dann aufgaben- und sprachübergreifend erfolgen. Bereits dokumentierte frühere Ausführungen sind historische Angaben, keine erneute Ausführungsanweisung.

**Nachfolgender Auftrag: Browserläufe bis Phase 4.** Für die ausdrücklich
beauftragte Integration der Schritte 01 bis 04 sind gezielte Image-Builds,
lokale Workflow-/Browserprüfungen und die dafür notwendige Entwicklungsanbindung
freigegeben. Der bestehende Hauptworkflow führt diese Schritte nun aus und
liefert deren Zwischenresultate je Modell beziehungsweise Referenzpaar an die
Auswertungsansicht. Dies ist keine Freigabe für neue Unit-/Komponententests oder
für die Implementierung der Phasen 5 und 6. Bedienung und lokale Image-Übernahme
stehen in der [Dagu-Dokumentation](../../dagu/README.md#im-browser-bis-phase-4-ausprobieren).

## Reihenfolge

| Schritt | Verantwortlicher Baustein | Arbeitsziel | Eingabe → Ausgabe |
|---|---|---|---|
| [01 – Eingabe vorbereiten](01-workflow-input.md) | API-Start und `workflow-data` | Modelleingaben sichern und `comparisonConfig` als erweiterbares Objekt vorsehen | Modellversionen, Aufgabe, Sprachdefinitionen, zunächst einfache Konfiguration → Eingabesnapshot |
| [02 – Graphen normalisieren](02-graph-parser.md) | `graph-parser` | Jeden Modellsnapshot in dieselbe Vergleichsstruktur überführen | Ein Modell aus dem Snapshot → Graph mit Herkunft und Diagnosen |
| [03 – Elementinventar extrahieren](03-model-label-extraction.md) | `model-label-extraction` | Vergleichbare Elemente und Texte konsistent bereitstellen | Ein Graph → vollständiges Inventar mit Vergleichstexten |
| [04 – Semantische Kandidaten ermitteln](04-synonym-matching.md) | `synonym-matching` | Kandidaten und Einzelwerte für ein Modellpaar liefern | Zwei Inventare → semantische Kandidatenmatrix |
| [05 – Modelle strukturell vergleichen](05-one-to-one-graph-matching.md) | `one-to-one-graph-matching` | Elemente zuordnen und Unterschiede nachvollziehbar bestimmen | Zwei Graphen und Kandidaten → Vergleich einer Referenz mit der Abgabe |
| [06 – Gesamtergebnis erzeugen](06-comparison-result.md) | Kleiner neuer Abschlussschritt `comparison-result` | Referenzvergleiche vollständig zusammenführen | Erwartete Referenzen und einzelne Ergebnisse → Gesamtergebnis |
| [07 – Workflow verbinden](07-dagu-workflow.md) | `model-evaluation-graph-matching` | Container, Abhängigkeiten, Status und Wiederholungen verbinden | Eingabesnapshot → ausgeführte Pipeline und benanntes Ergebnisartefakt |
| [08 – Ergebnis bereitstellen](08-result-integration.md) | Bestehende Auswertungs-API und Sidebar | Das Ergebnis zur richtigen Modellversion verständlich zugänglich machen | Laufstatus und Gesamtergebnis → kontrollierte API-Antwort und Anzeige |

Die ersten sechs Pakete entsprechen jeweils einem ausführbaren Verarbeitungsschritt. Paket 07 verbindet diese Schritte. Paket 08 schließt die bestehende Anwendung an. Zusätzliche HTTP-Dienste, Warteschlangen oder Datenbanken sind dafür nicht vorgesehen. `comparison-result` ist ein kurzlebiger Workflow-Container; der vorhandene Platzhalter `feedback-generation` bleibt der späteren Feedbackfunktion vorbehalten.

**Arbeitsgrenze für Paket 04:** Implementierung, eigene Methodenmodule und Workflow-Anbindung liegen unter `dagu/workflow-services/synonym-matching/`. `dagu/workflow-services/synonym-matching-louis/` dient ausschließlich als unveränderte Methodenreferenz. Benötigter Code darf daraus in den Zielordner übernommen und dort angepasst werden; im Referenzordner wird nichts bearbeitet. Der Zielcontainer ist ohne Laufzeitimport oder Quellcode-Mount dieses Referenzordners ausführbar. Einzelmethoden bleiben getrennt, der gemeinsame Ablauf wird übersichtlich zusammengeführt. Details und der Umgang mit einem abgebrochenen Umsetzungsversuch stehen in Paket 04.

**Arbeitsweise:** Zuerst die grundlegende Eingabehülle aus Paket 01 anlegen, dann 02 bis 06 nacheinander umsetzen und jeweils die Übergabe an den nächsten Schritt prüfen. Benötigt ein Schritt einen konkreten Konfigurationsparameter, werden dessen Bedeutung, Vorgabe und Validierung in diesem Schritt festgelegt und die Eingabedokumentation entsprechend ergänzt. Danach folgt die gemeinsame Ausführung in 07 und die Anzeige in 08. Ein vollständiger Parameterkatalog ist keine Voraussetzung für Paket 01.

## Gemeinsame Festlegungen

### Eingabe und Modellbezug

- Ein Lauf besitzt genau eine `evaluationId`, eine Abgabe und mindestens eine Referenz.
- Jede Modellquelle besitzt `key`, `role`, `label`, `modelId` und `versionId`.
- Die Abgabe heißt im Lauf `submission`; Referenzen heißen `reference_1`, `reference_2` usw. Die tatsächliche Herkunft ergibt sich immer aus `modelId` und `versionId`, nicht aus der lauflokalen Nummer.
- Ein Paar wird durch `pair: { "studentKey": "submission", "referenceKey": "reference_1" }` bezeichnet.
- Element-IDs sind Strings. Sie sind innerhalb eines Modellgraphen eindeutig. Modellübergreifend gehören Modellversion und Element-ID zusammen.
- Dieselbe Element-ID oder dasselbe Label in zwei Modellen beweist keine Entsprechung.
- Mehrere Referenzen gelten im geplanten Einstieg als vollständige Alternativen. Diese fachliche Annahme wird im zuständigen Paket 06 konkretisiert; ein entsprechender Konfigurationsparameter ist in Paket 01 noch nicht vorgeschrieben.

### Artefaktpfade

Alle Pfade sind relativ zu `/work/evaluations/<evaluationId>/`. Die vorhandene Workspace-Logik bleibt der Zugriffspunkt.

| Pfad | Erzeuger | Verbraucher |
|---|---|---|
| `inputs/evaluation-input.json` | 01 | Alle folgenden Schritte |
| `graphs/<modelKey>.json` | 02 | 03, 05 |
| `labels/<modelKey>.json` | 03 | 04 |
| `candidates/<referenceKey>.json` | 04 | 05 |
| `comparisons/<referenceKey>.json` | 05 | 06 |
| `results/comparison.json` | 06 | 07, 08 |

Der bestehende Ordnername `labels` bleibt erhalten; sein Inhalt wird zum vollständigen Elementinventar erweitert. Es gibt keine separate Dateikopie pro Vergleich für den Abgabegraphen oder dessen Inventar.

### Eigene Schrittergebnisse und Eingabereferenzen

`prepare_input` sichert den vollständigen Eingabesnapshot einmalig. Weitere Jobs
lesen benötigte Artefakte über den vorhandenen gemeinsamen Workspace; Dagu steuert
die Abhängigkeiten und übergibt Schlüssel beziehungsweise Pfade. Jeder Schritt
veröffentlicht nur sein eigenes Verarbeitungsergebnis mit notwendigen Eingabereferenzen,
Hashes, Modell-/Paarbezügen und eigener Erzeugerkennung. Vollständige Vorgängerartefakte
und deren Diagnosen werden nicht erneut eingebettet. Ein Vollständigkeitsstatus darf
Einschränkungen der Eingaben zusammenfassen; deren konkrete Ursachen bleiben über
die Eingabereferenzen nachvollziehbar.

Das ist für 02–04 implementiert und gilt als Vorgabe für die geplanten Schritte
05/06. Dort werden Zuordnungen beziehungsweise referenzübergreifende Auswahl neu
berechnet; vorhandene Graphen, Kandidaten und Einzelvergleiche bleiben referenziert.
Die spätere API-Projektion löst benötigte Referenzen für eine berechtigte Anzeige
auf, ohne die gespeicherten Workflow-Ergebnisse zu verändern.

### Austauschhülle und Versionen

Erfolgreiche Containeraufrufe nutzen weiterhin `workflow-result/v1`. Die fachlichen Inhalte liegen unter `result`. Beispiel einer gekürzten Hülle:

```json
{
  "schema": "workflow-result/v1",
  "schemaVersion": 1,
  "status": "ok",
  "capability": "graph-parser",
  "mode": "parse",
  "summary": "Modell normalisiert",
  "result": {
    "schema": "graph-result/v1",
    "evaluationId": "evaluation-1"
  }
}
```

`status: ok` bedeutet, dass der Schritt seinen Ergebnisvertrag geliefert hat. Fachliche Unvollständigkeit wird im Ergebnis beschrieben und nicht aus dem Prozess-Exitcode abgeleitet.

| Inhalt | Geplanter Vertrag |
|---|---|
| Eingabesnapshot | `evaluation-input/v1`, `schemaVersion: 1` |
| Parserergebnis | `result.schema: graph-result/v1`, darin `graph.schemaVersion: 1` |
| Elementinventar | `result.schema: element-inventory/v1` |
| Semantische Evidenz | `result.schema: semantic-candidates/v1` |
| Einzelvergleich | `result.schema: reference-comparison/v1` |
| Gesamtergebnis | `result.schema: comparison-result/v1` |

**Erster Release: Alle geplanten Austauschformate verwenden V1.** Die Pipeline wird initial eingerichtet und ist noch nicht produktiv eingesetzt. Bestehende Formatdefinitionen dürfen daher bei der Umsetzung direkt durch den geplanten V1-Stand ersetzt werden; bestehende Entwicklungsartefakte müssen nicht durch Migrationen, Konvertierungen oder parallele Altformat-Unterstützung erhalten werden. Erzeuger und direkte Verbraucher werden gemeinsam auf denselben V1-Vertrag abgestimmt. Dafür ist kein Versionssprung auf V2 oder V3 vorgesehen.

Für die Umsetzung gelten die hier konkretisierten Austauschfelder; beispielsweise wird die vollständige Referenzliste einschließlich fehlender Ergebnisse unter `referenceResults` geführt. Ausgenommen sind die noch vorläufigen Unterfelder und Parameter von `comparisonConfig`, die erst im zuständigen Arbeitsschritt festgelegt werden. Die JSON-Ausschnitte in den Paketen zeigen jeweils den Inhalt von `result`, sofern nicht ausdrücklich der Eingabesnapshot gemeint ist. Auslassungen werden im Begleittext benannt.

### Workflow-Auswahl und vorläufige Konfigurationsreferenz

Unterschiedliche Auswertungsabläufe können weiterhin als unterschiedliche Workflows definiert werden. Der ausgewählte Workflow bestimmt die ausgeführten Schritte und ihre Abhängigkeiten. `comparisonConfig` ermöglicht ergänzend die Parametrisierung dieses Workflows beziehungsweise einzelner Schritte. Sie ersetzt die Workflow-Auswahl nicht durch einen universellen, vollständig parametergesteuerten Ablauf.

**Für Paket 01 ist nur festgelegt:** Der Eingabesnapshot besitzt ein JSON-Objekt `comparisonConfig`. Es darf zunächst leer sein:

```json
{
  "comparisonConfig": {}
}
```

**Die folgende Übersicht ist eine Vergleichs- und Planungsreferenz, kein finales Eingabeschema und keine Liste verpflichtender Parameter.** Auch die entsprechenden Feldpfade und Beispielwerte in den weiteren Paketen sind vorläufige Vorschläge. Namen, Aufteilung und tatsächlicher Bedarf werden im jeweils zuständigen Arbeitsschritt bestimmt.

| Möglicher Bereich | Möglicher Inhalt | Zuständiger Schritt |
|---|---|---|
| `normalization` | Nur bei tatsächlichem Bedarf allgemeine Übersetzungsoptionen; keine sprachspezifische Profilpflicht | 02 |
| `semantics` | Verfahren, Textvorbereitung, Kombination und gegebenenfalls Aliaswissen | 04 |
| `matching` | Vergleichskriterien, Gewichte, Schwellen und Evidenzregeln | 05 |
| `referencePolicy`, `selection` | Bedeutung mehrerer Referenzen und deren Auswahl | 06 |
| `limits` | Tatsächlich benötigte Eingabe- und Ausführungsgrenzen | Je betroffener Schritt, Laufzeitintegration in 07 |
| `disclosure` | Zulässige Informationen in der Ergebnisanzeige | 08 |

Ein Parameter wird erst aufgenommen, wenn ein Verarbeitungsschritt ihn tatsächlich benötigt. Mit seiner Einführung werden in demselben Arbeitsschritt sein Name und Datentyp, seine Bedeutung, seine Pflicht-/Optionalität, ein gegebenenfalls nötiger Standardwert und die Validierung festgelegt. README, Workflow-Input und betroffene Übergaben werden dabei gemeinsam nachgetragen. Paket 01 erhält dadurch schrittweise konkretere Anforderungen; es legt sie nicht vorab für alle Nachfolger fest.

Die Initialisierung übernimmt das Objekt verlustfrei und prüft zunächst nur seine grundlegende Form. Sie verlangt keine noch nicht eingeführten Unterbereiche und verwirft keine ihr unbekannten Einträge. Die fachliche Prüfung konkreter Parameter gehört zum verarbeitenden Schritt. Das ist kein Auftrag für ein allgemeines Konfigurationsframework.

**Unveränderlich pro Lauf, erweiterbar während der Entwicklung:** Der für einen Lauf übergebene Konfigurationsstand wird mit dessen Snapshot gesichert. Spätere Ergänzungen gelten für neue Läufe. Die jeweils tatsächlich verwendeten Regeln und Standardwerte werden durch den zuständigen Schritt nachvollziehbar dokumentiert. Profilinhalte und Ressourcen sind bei ihrer Einführung durch Snapshot oder unveränderliche Verarbeitungsversion eindeutig zu bestimmen; unbemerkte Änderungen während desselben Laufs sind ausgeschlossen.

### Allgemeiner Parser ohne Sprachprofil

Paket 02 benötigt keine zusätzlichen Konfigurationsparameter. Bekannte mitgelieferte Definitionen benötigen keine zusätzliche Freischaltung. Das allgemeine V1-Parserergebnis erhält Modellstruktur, native Typen und Sprachherkunft. `languageResources` dokumentiert die Definitionsstände mit ihren Inhaltshashes; `producer.resourceHash` identifiziert die allgemeine Verarbeitung. Beide fließen in `graphHash` ein und dienen ausschließlich der Herkunftsdokumentation. Ein sprachspezifischer Profilhash wird nicht eingeführt. Der [Servicevertrag](../../dagu/workflow-services/graph-parser/README.md) beschreibt die korrigierte V1-Übergabe.

### Elementinventar ohne neue Konfiguration

Paket 03 prüft und übernimmt genau dieses Parserergebnis als
`element-inventory/v1`. Alle `semantic`- und `unsupported`-Element-/Beziehungsknoten
bleiben mit ihren Graph-IDs erhalten, auch ohne Label. Ausdrücklich strukturelle
Knoten und technische Kanten werden keine Labelkandidaten. Originallabel, Typen,
Sprachbindung und Parserdiagnosen bleiben ausschließlich im Graphartefakt.
Das Inventar speichert je ID nur `matchText`, `labelStatus` und `textLanguage`;
`graphPath` und `graphHash` referenzieren die Eingabe innerhalb der `evaluationId`.
Modellquelle und `inputHash` sichern den Modell-/Snapshot-Bezug. Eigene Textdiagnosen
werden nicht mit Parserdiagnosen vermischt; der Vollständigkeitsstatus berücksichtigt
weiterhin die Eingabe. `producer` benennt den Inventarerzeuger; `inventoryHash`
bindet dessen Ausgabe an diese Grundlage. `textLanguage` bezeichnet eine bekannte
natürliche Sprache und bleibt beim aktuellen Parser `null`. Es gibt keine neuen
Konfigurationsparameter. Der [Servicevertrag](../../dagu/workflow-services/model-label-extraction/README.md)
legt die tatsächliche Ein-/Ausgabe und die konservative Textaufbereitung fest.

### Semantische Kandidaten ohne neue Eingabeparameter

Paket 04 ist unter `synonym-matching` implementiert. Der nach ausdrücklichem Auftrag
gezielt wiederhergestellte Ordner `synonym-matching-louis` bleibt ausschließlich
Methodenreferenz. Vier eigene Methodenmodule übernehmen Levenshtein, Jaro-Winkler,
Zeichen-Trigramme und das bestehende multilinguale Embedding mit 50:50-Fusion.
`comparisonConfig: {}` genügt; `semantics` darf fehlen oder leer sein. Nicht
unterstützte semantische Einstellungen werden abgewiesen, andere Bereiche bleiben
ihren zuständigen Schritten vorbehalten. Neue fachliche Parameter entstehen nicht.

Ein Aufruf liest `labels/submission.json` und genau `labels/<REFERENCE_KEY>.json`,
prüft Quellen und Inventarhashes und schreibt `candidates/<REFERENCE_KEY>.json` als
`semantic-candidates/v1` in `workflow-result/v1` mit Capability `synonym-matching`.
`inventoryPaths` und `inventoryHashes` referenzieren beide Inventare; vollständige
Inventare und Graphknoten werden nicht erneut eingebettet. Matrixzeilen nennen
`referenceElementId`, Kandidaten `submissionElementId`; deren Modellbezug folgt aus
`pair`. Alle verwendbaren Paarwerte, die Rechenregel, tatsächliche Methodentexte
und Ressourcenstände bleiben erhalten. Diagnosen enthalten nur eigene Hinweise,
der Vollständigkeitsstatus berücksichtigt weiterhin beide Inventare.
Fehlende Texte werden explizit gekennzeichnet. `threshold: null` und
`filtered: false` kennzeichnen die vollständige Evidenz. Der [Servicevertrag](../../dagu/workflow-services/synonym-matching/README.md)
beschreibt die genaue Ein-/Ausgabe, Offline-Ressourcen und Fehlerbehandlung.
Die Umsetzung wurde ausschließlich statisch durchgesehen.

### Herkunft

Ein `producer`-Eintrag hält Serviceversion und unveränderliche Image- beziehungsweise Ressourcenkennung fest. Er ist Metadatum und kein fachlicher Graphinhalt.

Hashes verbinden die Übergänge: `inputHash`, `graphHash`, `inventoryHash`, `semanticConfigHash`, `candidateHash` und `matchingConfigHash`. Jeder Hash bezieht sich auf den benannten Inhalt, ohne sein eigenes Hashfeld und ohne Zeitstempel oder Laufzeitmessungen. Schlüssel werden kanonisch geordnet; Mengen werden stabil nach Identität geordnet, fachlich geordnete Listen behalten ihre Reihenfolge. Ein Graphhash umfasst Quelle, Graph, verwendete Sprachdefinitionen, die allgemeine Verarbeitungsversion und Interpretationsdiagnosen. Dafür ist kein sprachspezifischer `profileHash` erforderlich.

Es wird keine neue Cacheplattform aufgebaut. Wiederverwendung erfolgt zunächst innerhalb desselben Laufs und bei Wiederholungen desselben Schritts.

### Vollständigkeit, Diagnosen und Fehler

**Implementierter Vergleichsbereich, ausschließlich statisch durchgesehen:** Graph und Folgeinventare enthalten ausschließlich den rekursiven fachlichen Inhalt des Modeling-Layers. Die ersten beiden direkten Kinder der eindeutigen Canvas-Wurzel sind in Exportreihenfolge Modeling- und Feedback-Layer. Canvas-Wurzel, technische Layer, Feedback und sonstige Inhalte außerhalb dieses Bereichs sind keine Vergleichselemente. Verbindungen zu ausgeschlossenen Zellen samt ihren Kindbeschriftungen bleiben ebenfalls ausgeschlossen; tatsächlich fehlende Endpunktzellen bleiben diagnostizierbare offene Enden. Fachliche Container und unbekannte Modellbestandteile innerhalb des Modeling-Layers bleiben erhalten. `graph.excluded` bleibt als leeres V1-Feld bestehen; `COMPARISON_SCOPE` ist ein einmaliger informativer Bereichshinweis. Reguläre Ausschlüsse erzeugen keine Interpretationslücke; Sprachbeobachtungen gelten nur für übernommene Knoten. Fehlende oder beschädigte Plattformstruktur erzeugt einen technischen Eingabefehler, ein gültiger leerer Modeling-Layer einen leeren Graphen. Regeln, statisch erfüllte Kriterien und offene Grenzen stehen in [Paket 02](02-graph-parser.md#nachfolgende-präzisierung-vergleichsbereich-modeling-layer). Die V1-Verträge und der vollständige Eingabesnapshot bleiben bestehen; Beschriftungsnormalisierung und Synonymverfahren wurden für diese Abgrenzung nicht geändert. Dieser begrenzte Auftrag umfasst ausdrücklich keine Laufzeit-, Test-, Build-, Lint- oder Syntaxprüfungen; frühere Browserfreigaben belegen den neuen Stand nicht.

Die folgenden Dimensionen werden getrennt verwendet:

| Dimension | Werte | Bedeutung |
|---|---|---|
| Technische Abdeckung | `complete`, `partial`, `unavailable` | Wurden alle benötigten Verarbeitungsschritte erfolgreich geliefert? |
| Interpretation | `complete`, `partial`, `unavailable` | Können alle relevanten Modellbestandteile anhand der mitgelieferten Definitionen interpretiert werden? |
| Zuordnung | `complete`, `partial`, `unavailable` | Sind alle Zuordnungsfragen entschieden? Auch eindeutig fehlende Elemente sind eine Entscheidung. |

Ein unbekannter Typ kann die Interpretation einschränken. Zwei gleich plausible Kandidaten schränken die Zuordnung ein. Ein nicht gestarteter Container ist eine technische Einschränkung. Keiner dieser Fälle wird allein zu einem studentischen Fehler. Gibt es überhaupt keine nutzbaren Vergleichsergebnisse, sind Interpretation und Zuordnung im Gesamtergebnis `unavailable`; erfolgreiche Parser- und Inventarartefakte verwenden dagegen nur `complete` oder `partial` für ihre Interpretation.

Die Modellierungssprache wird je Element und modellierter Beziehung neutral erhalten. Eine eindeutig erkannte weitere Sprache ist von mehrdeutiger oder fehlender Sprachherkunft zu unterscheiden und macht die Interpretation nicht allein unvollständig. Mehrere mitgelieferte Sprachdefinitionen belegen noch keine tatsächliche Verwendung oder unzulässige Vermischung. Paket 02 gibt für tatsächlich erkannte unterschiedliche Sprach-IDs die neutrale Information `MULTIPLE_LANGUAGE_ORIGINS` aus; sie ändert die Vollständigkeit nicht. Die fachliche Beurteilung und daraus abgeleitetes Feedback gehören nicht zum Parser.

Diagnosen enthalten mindestens `code`, `severity`, `scope`, `message` und betroffene Modell-/Elementreferenzen. Ein nicht vergleichbarer Bereich bleibt identifizierbar.

Technische Fehler führen zu einem Exitcode ungleich null und verständlichen Angaben auf stderr. Es wird dann kein erfolgreiches Ergebnis am regulären Artefaktpfad veröffentlicht. Bereits erfolgreiche unabhängige Artefakte bleiben bestehen. Der abschließende Schritt erkennt fehlende Ergebnisse anhand der im Snapshot erwarteten Referenzen; genaue Prozessfehler kommen aus Dagu und werden in der API zugeordnet.

Unveränderliche Ergebnisdateien enthalten keine wechselnden Laufzeitangaben. Wiederholung vor dem Laufabschluss darf denselben Inhalt erneut bestätigen. Abweichender Inhalt am selben Pfad ist ein Konflikt. Nach Veröffentlichung des Gesamtergebnisses beginnt eine erneute Auswertung mit einer neuen `evaluationId`.

### Gemeinsames fachliches Beispiel

Das Beispiel aus dem Gesamtkonzept begleitet die Übergaben:

- `Verkauf` enthält die Klassen `Angestellter` beziehungsweise `Mitarbeiter`, `Auftrag` und `Position`.
- Das Attribut `Menge` gehört in der Referenz zu `Position`, in der Abgabe zu `Auftrag`.
- `Kontakt` in der Abgabe ist gegenüber den Referenzattributen `Telefon` und `E-Mail` nicht eindeutig.
- Die Beziehungen zwischen Beschäftigtem und Auftrag sowie zwischen Auftrag und Position sind vergleichbar.

Das Beispiel erläutert eine begründete Synonymzuordnung, einen eigenen Befund zur falschen Zugehörigkeit und eine offene Kandidatengruppe. Es enthält keine berechneten Qualitätskennzahlen und ist ausschließlich eine konzeptionelle Illustration. Seine Begriffe und Strukturen begründen weder besondere Parserregeln noch eine auszuführende Testaufgabe.

## Erfüllungskriterien ohne Testausführung

Pro Paket sind Arbeitsziel, Liefergegenstand und Erfüllungskriterien maßgeblich. Sie beschreiben das zu implementierende Verhalten, nicht automatisch auszuführende Prüfungen. Aktuell wird ausschließlich statisch anhand der Änderungen beurteilt, ob die Zuständigkeiten und Schnittstellen dazu passen. Nicht ausgeführte Laufzeitprüfungen werden ausdrücklich als solche benannt.

Auch die Abschlussintegration wird derzeit nicht gestartet. Eine spätere gesonderte Verifikation soll beliebige Aufgaben und mitgelieferte Sample Solutions über denselben generischen Ablauf berücksichtigen. Weder Laufzeitfunktion noch semantische Qualität werden ohne einen solchen Auftrag und entsprechende Nachweise als getestet ausgegeben.

## Entscheidungen vor der Umsetzung

Paket 01 legt die Modelleingaben und das erweiterbare Konfigurationsobjekt an. Allgemeine Übersetzung vorhandener Typen, Container und Kindbestandteile wird in 02, semantische Einstellungen in 04, Matchingregeln in 05, Referenzbedeutung und Auswahl in 06 sowie die Offenlegung in 08 konkretisiert. Es wird keine erste unterstützte Sprache ausgewählt. Erst bei tatsächlichem allgemeinen Parameterbedarf werden Eingabevertrag und Dokumentation ergänzt. Die vorgeschlagenen Matching-Schwellen bleiben vorläufige Planungswerte. Datensammlung, Testkampagnen und Probeläufe sind aktuell nicht beauftragt.

**Umsetzungsstand:** Pakete 01–04 sind umgesetzt; frühere Nachweise und ihre Grenzen
stehen im Eingabepaket. Der korrigierte Parserstand, das Elementinventar und die
semantische Paarverarbeitung sind ausschließlich statisch durchgesehen.
`comparisonConfig` bleibt beim API-Start ein leeres, erweiterbares Objekt; Pakete
02–04 führen keine zusätzlichen fachlichen Parameter ein. Alle Formate bleiben V1.
Pakete 05/06 und deren vollständige Integration in 07/08 sind weiterhin geplant.
Der Hauptworkflow und die API-/JSON-Anzeige sind bereits bis Phase 4 verbunden;
der Abschluss liefert derzeit `evaluation-preview/v1` statt eines fachlichen
`comparison-result/v1`. Die jüngsten Änderungen an Parser und kompakten Artefakten
sind ausschließlich statisch durchgesehen; dafür wurden keine Images neu gebaut
und keine Läufe ausgeführt. Semantische Qualität und betriebliche Grenzen bleiben offen.
