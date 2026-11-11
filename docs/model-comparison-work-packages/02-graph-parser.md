# 02 – Graph-Parser zur gemeinsamen Vergleichsgrundlage ergänzen

**Baustein:** Container `graph-parser`, interner Workflow `graph-parser-model`.

**Abhängigkeit:** [01 – Eingabe vorbereiten](01-workflow-input.md). Es gelten die [gemeinsamen Verträge](README.md).

**Stand:** Paket 02 ist einschließlich der Modeling-Layer-Abgrenzung generisch umgesetzt und ausschließlich statisch durchgesehen. Frühere Ausführungen belegen diesen Stand nicht; seine Laufzeitfunktion ist ungetestet. Die Folgepakete behalten ihren separat dokumentierten Stand.

## Arbeitsziel

Jedes Modell wird unabhängig von seiner Rolle als Abgabe oder Referenz in dieselbe fachlich interpretierbare Graphstruktur überführt. Identität, Zugehörigkeiten, Beziehungen und Herkunft bleiben so erhalten, dass spätere Schritte einen falsch platzierten Bestandteil erkennen können. Für Elemente und modellierte Beziehungen wird außerdem nachvollziehbar erhalten, welcher Modellierungssprache und Sprachversion sie zugeordnet werden können. Eine erkennbare andere Sprachherkunft, eine mehrdeutige Zuordnung und eine fehlende Zuordnung sind unterschiedliche Aussagen.

### Nachfolgende Präzisierung: Vergleichsbereich Modeling-Layer

**Stand dieser Änderung:** Implementiert gemäß [Folgeprompt](02-modeling-layer-scope-prompt.md), ausschließlich statisch durchgesehen. Die unten markierten Kriterien beschreiben die Implementierung, keinen Laufzeitnachweis.

Der Vergleichsgraph bildet ausschließlich den fachlichen Inhalt des definierten Modeling-Layers ab. Der Parser bestimmt diesen Bereich vor der fachlichen Typ- und Sprachauflösung. Die Plattformstruktur bestimmt den Layer, nicht eine Modellierungssprache, ein Label oder eine feste Zell-ID. Im aktuellen Editor ist der erste direkte Kindknoten der Canvas-Wurzel der Modeling-Layer, der zweite der Feedback-Layer.

**Statisch nachvollzogene Zuordnung:** `ensureGraphLayers` und `syncLayerReferences` in [DrawingCanvas.vue](../../web/src/components/modeling/canvas/DrawingCanvas.vue) verwenden `root.getChildAt(0)` beziehungsweise `root.getChildAt(1)`. [modelPersistence.ts](../../web/src/utils/modelPersistence.ts) exportiert über den vorhandenen maxGraph-Serializer; dessen `ModelCodec`/`Codec.encodeCell` schreibt die Kinder samt Teilbäumen in gespeicherter Reihenfolge. Der vorhandene [Laborverwaltungs-Export](../../api/src/modeling_api/db/migrations/versions/v12_laboratory_management/sample_solution.json) zeigt entsprechend erst den Modeling-Layer mit Inhalten und danach den Feedback-Layer. Der Parser filtert deshalb direkte Wurzelkinder über `parent` in XML-Reihenfolge, ohne nach IDs zu sortieren. Er verlangt genau eine elternlose Canvas-Wurzel und mindestens zwei direkte Kinder; Wurzel und beide vorgesehenen Layer dürfen weder Vertex noch Edge sein.

- Canvas-Wurzel und beide Layer sind technische Infrastruktur. Sie werden keine Vergleichsknoten und erzeugen keine `contains`-Kanten.
- Nur Inhalte des Modeling-Layers werden rekursiv übernommen. Fachliche Container, ihre Kindbestandteile und deren unmittelbare Zugehörigkeiten bleiben erhalten. Oberste Modellbestandteile besitzen im Vergleichsgraphen keinen künstlichen Layer-Besitzer.
- Feedback-Layer und dessen gesamter Teilbaum sowie sonstige Inhalte außerhalb des Modeling-Layers bleiben außerhalb des Vergleichs. Bereits ausdrücklich als Feedback gekennzeichnete Inhalte innerhalb des Modeling-Layers bleiben ebenfalls ausgeschlossen.
- Modellierte Verbindungen innerhalb des Bereichs bleiben mit ihren fachlichen Anschlüssen erhalten. Verbindungen zu nachweislich ausgeschlossenen Zellen sowie ihre zugehörigen Beschriftungen werden nicht übernommen. Eine tatsächlich fehlende Endpunktzelle innerhalb einer ansonsten relevanten Verbindung bleibt dagegen ein diagnostizierbares offenes Ende.
- Unbekannte oder mehrdeutig definierte Inhalte innerhalb des Modeling-Layers bleiben erhalten und werden weiterhin neutral diagnostiziert. Die Bereichsauswahl ist keine fachliche Bereinigung.
- Reguläre Infrastruktur und Inhalte außerhalb des Vergleichsbereichs benötigen keine Einzeleinträge mit vollständigen XML-Daten in `graph.excluded` und keine Einzeldiagnosen. Ein kurzer Hinweis auf den Vergleichsbereich genügt. Das bestehende V1-Feld `graph.excluded` bleibt für gegebenenfalls tatsächlich erklärungsbedürftige Ausschlüsse erhalten und darf leer sein.
- Vollständigkeit und Sprachbeobachtungen beziehen sich auf die übernommenen Modellbestandteile. Regulär ausgeschlossene Infrastruktur oder Feedback machen die Interpretation nicht `partial`.
- Kann der Modeling-Layer wegen einer fehlenden oder beschädigten Plattformstruktur nicht eindeutig bestimmt werden, entsteht ein technischer Eingabefehler. Es gibt keinen stillen Rückfall auf sämtliche übrigen Zellen. Ein vorhandener leerer Modeling-Layer ist dagegen ein gültiges leeres Modell.

Der einzige reguläre Bereichshinweis lautet `COMPARISON_SCOPE` mit `severity: info` und Modellbezug. `graph.excluded` wird als leere V1-Liste ausgegeben. Für den vorhandenen eigenständigen Demo-Modus wurde nur das synthetische XML um dieselbe gültige Canvas-/Layerstruktur ergänzt; gespeicherte Modelle und Eingabesnapshots werden nicht verändert.

Die nachfolgenden Inventar- und Matching-Schritte verwenden diese begrenzte Elementmenge. Der vollständige Eingabesnapshot bleibt unverändert erhalten; ausgeschlossene Infrastruktur wird nicht in Folgeartefakten erneut aufgebaut. Schema und Hüllen bleiben V1. Die Layer-Abgrenzung ändert keine Beschriftungsaufbereitung, Methoden oder Scores. Im anschließenden Auftrag wurden ausschließlich Datenkopien durch Referenzen ersetzt; berechnete Kandidaten werden nicht gekürzt. Die aktuellen kompakten Folgeformate stehen in den Paketen 03 und 04.

Der Parser beschreibt die vorgefundenen Daten neutral. Er entscheidet weder, ob eine verwendete Sprache für die Aufgabe zulässig ist, noch erzeugt er Feedback oder Punkteabzüge.

**Verbindlicher Umfang:** Derselbe Parser muss jede Aufgabe mit ihren Abgaben und Sample Solutions im vorhandenen Modellformat anhand der jeweils mitgelieferten Sprachdefinitionen verarbeiten. Es gibt keine Pilotsprache, kein festes UML-Profil, keine sprachspezifischen Typ-Mappings und keine Erkennung bestimmter Definitionen anhand fest einprogrammierter Ressourcenhashes. `comparisonConfig: {}` bleibt ohne manuelle Freischaltung von Typen oder Sprachen verwendbar.

**Aktuell keine Tests oder Probeläufe:** Dieses Paket wird ohne Testausführung, Testdateien, manuelle Modell-/Containerläufe, Builds, Lint- oder Syntaxprüfungen umgesetzt beziehungsweise korrigiert. Die Erfüllungskriterien werden nur statisch anhand der Änderungen durchgesehen. Die Bereinigung gemäß dem [Korrekturauftrag](02-graph-parser-correction-prompt.md) ist im aktuellen Arbeitsstand enthalten; die Laufzeitfunktion bleibt ungetestet.

## Ausgangslage und relevante Stellen

[parser.py](../../dagu/workflow-services/graph-parser/src/parser.py) normalisiert maxGraph-XML und löst die mitgelieferten Sprachdefinitionen allgemein auf. [main.py](../../dagu/workflow-services/graph-parser/src/main.py) bindet den Parser an den eingefrorenen Snapshot aus Schritt 01 an. Offene Enden und mehrdeutige Definitionen bleiben mit lokalisierten Diagnosen erhalten. Jede modellierte Beziehung besitzt einheitlich einen Beziehungsknoten und technische Anschlusskanten.

Die Umsetzung ergänzt den vorhandenen Parser; es gibt keinen zweiten unabhängigen XML-Parser für Matchingzwecke.

## Was kommt hinein?

- `WORKFLOW_EVALUATION_ID` und `MODEL_KEY` wählen genau ein Modell aus `inputs/evaluation-input.json`.
- Der Modellsnapshot enthält das XML und seine festgelegten Sprachversionen einschließlich eingebundener Sprachen. Alle für dieses Modell mitgelieferten Definitionen werden gleichberechtigt zur Herkunftsauflösung berücksichtigt.
- `comparisonConfig` darf leer sein. Ein Bereich `normalization` wird nur ergänzt, wenn eine tatsächlich benötigte allgemeine Option entsteht; ein Sprachprofil oder eine Mappingliste ist keine Voraussetzung.
- `WORKFLOW_OUTPUT_PATH` benennt `graphs/<modelKey>.json`.

Ein eigenständiger Aufruf erhält denselben vollständigen `evaluation-input/v1`-Snapshot einschließlich `inputHash` unter `input` und wählt das Modell über `modelKey` (Standard `submission`). Es gibt keinen Zugriff auf aktuelle Datenbankstände oder veränderliche Sprachdefinitionen.

## Was kommt heraus?

Eine `workflow-result/v1`-Hülle mit `capability: graph-parser` und folgendem Inhalt:

| Feld in `result` | Bedeutung |
|---|---|
| `schema` | `graph-result/v1` |
| `evaluationId`, `source` | Lauf und vollständige Modellquelle |
| `inputHash`, `producer` | Eingabebezug und Version der allgemeinen Verarbeitung |
| `languageResources` | Zum Modell mitgelieferte Sprachversionen samt Inhaltshash ihrer Definitionsdaten; Herkunftsdokumentation ohne Typfreischaltung |
| `graphHash` | Identität des Graphen einschließlich Quelle, verwendeter Definitionen, allgemeiner Verarbeitungsversion und Interpretationsdiagnosen; kein sprachspezifischer Profilhash erforderlich |
| `graph` | `schemaVersion: 1`, mitgelieferte Sprachreferenzen, Knoten und Kanten ausschließlich aus dem Vergleichsbereich; `excluded` enthält keine vollständige Inventarisierung regulär ausgeschlossener Infrastruktur |
| `completeness.interpretation` | `complete` oder `partial`: Abdeckung der strukturellen Übersetzung und Definitionsauflösung, keine Bewertung der Sprachwahl oder fachlichen Richtigkeit |
| `diagnostics` | Konkrete Einschränkungen und gegebenenfalls neutrale Beobachtungen mit Original- und Sprachbezug; nicht jede Diagnose bedeutet unvollständige Interpretation |

### Knoten

| Feld | Bedeutung |
|---|---|
| `id` | Ursprüngliche Zell-ID oder deterministisch erzeugte Identität |
| `kind` | `element` oder `connection` |
| `type`, `nativeType` | `type` stammt aus der eindeutig aufgelösten Definition und bleibt andernfalls `null`; `nativeType` erhält die ursprüngliche Modellangabe. Keine fest einprogrammierte Typübersetzung. Die eindeutige Typidentität umfasst den Sprach-/Definitionsbezug |
| `label` | Unverändertes ursprüngliches Label |
| `properties` | Vorhandene fachliche Eigenschaften; Werte und Datentypen nur anhand ihrer expliziten Daten-/Definitionsangaben übernehmen, nicht durch sprachspezifische Vermutungen |
| `language` | Erkannte Modellierungssprache als `{ languageId, versionId }`; `null`, wenn sie nicht eindeutig bestimmbar ist |
| `languageResolution` | `resolved`, `ambiguous` oder `unresolved` für die Sprachherkunft |
| `definition`, `definitionCandidates` | Eindeutige Sprachdefinition beziehungsweise mögliche Definitionen |
| `comparisonRole` | `semantic`, `structural` oder `unsupported` |
| `origin` | Originalzell-IDs, gegebenenfalls Feld-/Textreferenz und verwendete Transformationsregel |
| `directed` | Nur für Beziehungsknoten: `true`, `false` oder `null` |

Eindeutig definierte Inhalte sind standardmäßig `semantic`. `structural` wird nur aus einer ausdrücklichen Rollenangabe der Zelle oder der aufgelösten Definition übernommen, niemals aus einem Typnamen, einer Form oder einer vermuteten Bedeutung als Attributfach. Nicht eindeutig definierte Inhalte bleiben `unsupported` und werden nicht automatisch ausgeschlossen.

**Parent-Kontext, implementiert und nur statisch durchgesehen:** Deklarierte `children` und `additionalLabels` werden nach ihren Parents unabhängig von Zell-ID-Reihenfolgen aufgelöst. Eine passende Kinddefinition hat Vorrang vor eigenständigen Kandidaten; ohne passende Kinddefinition bleiben eigenständige Definitionen verfügbar, auch bei fachlich falscher Platzierung. Sprachbindung, Vergleichsrolle und Kantenklassifikation folgen der ausgewählten Definition. Nicht eindeutig auflösbare deklarierte Childs erhalten `UNRESOLVED_CHILD_DEFINITION` und bleiben `unsupported` bei `interpretation: partial`. `AMBIGUOUS_DEFINITION` ist mehreren eigenständigen Definitionen vorbehalten. Ein fehlender Parent oder mehrere Kandidaten im Parent-Kontext werden nicht durch eine willkürliche Auswahl verdeckt.

### Sprachherkunft und nicht zuordenbare Bestandteile

`graph.languages` bezeichnet die zum Modell mitgelieferten Sprachreferenzen. Daraus allein folgt nicht, dass jede Sprache tatsächlich im Modell verwendet wurde. Die tatsächliche Verwendung ergibt sich aus den Sprachzuordnungen der Element- und Beziehungsknoten. Die natürliche Sprache eines Labels, beispielsweise Deutsch, ist davon unabhängig.

Die Herkunft wird aus einer eindeutig auflösbaren Sprachdefinition oder einer belastbaren ursprünglichen Sprachreferenz bestimmt. Bezeichnung, Farbe oder Form eines Elements sind kein Beweis für seine Modellierungssprache. Ohne ausreichende Evidenz wird keine Sprache erraten. Eine eindeutige Definition verweist mit `languageId`, `versionId` und `path` auf die mitgelieferte Definition.

| Vorliegender Fall | Darstellung und Bedeutung |
|---|---|
| Eindeutige Definition in einer Sprache | `languageResolution: resolved`; `language` und `definition` benennen die Herkunft |
| Eindeutige Definition in einer weiteren Sprache, etwa ein ERD-Element neben SEM-Elementen | Ebenfalls `resolved`; die tatsächliche ERD-Herkunft bleibt erhalten. Allein daraus folgt weder ein Modellfehler noch `interpretation: partial` |
| Definitionen mehrerer Sprachen kommen gleichberechtigt infrage | `languageResolution: ambiguous`, `language: null`; `definitionCandidates` erhält die möglichen Definitionen einschließlich ihrer Sprachreferenzen |
| Keine Definition und keine belastbare Sprachherkunft bestimmbar | `languageResolution: unresolved`, `language: null`; Element mit Originaltyp und Diagnose erhalten |
| Mehrere mögliche Definitionen, aber alle gehören zu derselben Sprachversion | Sprachherkunft kann `resolved` sein; die Definitionszuordnung bleibt über `definition: null` und `definitionCandidates` ausdrücklich mehrdeutig |

Eine erkannte Sprachherkunft und eine eindeutig auflösbare Typdefinition sind verschiedene Dinge. Eine belastbare ursprüngliche Sprachreferenz kann auch dann erhalten bleiben, wenn die konkrete Typdefinition nicht auflösbar ist. Eine gültige mitgelieferte Definition benötigt dagegen keine zusätzliche Registrierung in einem Vergleichsprofil: Das Fehlen einer solchen Mappingregel ist kein Grund für `unsupported` oder eine Interpretationswarnung.

Für modellierte Beziehungen gilt dieselbe Herkunftsauflösung wie für Elemente. Eine Verbindung zwischen Elementen verschiedener Sprachen übernimmt nicht automatisch die Sprache eines Endpunkts. Erzeugte technische `contains`-/`endpoint`-Kanten stellen dagegen keine eigenständige verwendete Modellierungssprache dar; sie verweisen über ihre Herkunft auf die beteiligten Originalelemente. Vorhandene Kind- und Attributzellen bleiben mit ihrer belegbaren Sprachherkunft erhalten; aus freien Labels werden keine zusätzlichen Attributknoten erzeugt.

**Entscheidung zur neutralen Sprachbeobachtung:** Tatsächlich erkannte unterschiedliche Sprach-IDs erzeugen `MULTIPLE_LANGUAGE_ORIGINS` mit `severity: info`, betroffenen IDs und Sprachreferenzen. Diese Information ändert die Vollständigkeit nicht und bewertet die Sprachwahl nicht. Unterschiedliche Versionen derselben Sprache zählen dabei nicht als mehrere Sprachen. Auch wenn ein Modell vollständig aus einer anderen Sprache stammt, liefern seine Herkunftsreferenzen bereits die Grundlage für einen späteren Abgleich mit der Aufgabe.

Eingebundene Sprachen können absichtlich zusammengehören. Auch unterschiedliche Versionen derselben Sprache sind nicht automatisch verschiedene Modellierungssprachen. Die im Snapshot verfügbaren oder von einer Aufgabe eingebundenen Sprachen sind kein ungeprüfter Katalog verbotener beziehungsweise erlaubter Sprachkombinationen. Ob und wie ein Vergleich mit einer ausdrücklich geforderten Aufgabensprache erfolgt und welches Feedback daraus entsteht, bleibt einer nachgelagerten fachlichen Regel vorbehalten. Dieser optionale Prüfpunkt führt jetzt keinen zusätzlichen Pflichtparameter in `comparisonConfig` ein.

### Bedeutung von Vollständigkeit und Diagnosen

`completeness.interpretation` bleibt Bestandteil des Plans. `complete` bedeutet, dass die relevanten Modellbestandteile nach den verfügbaren Regeln zuverlässig aufbereitet wurden. `partial` kennzeichnet konkrete Auflösungslücken oder nicht unterstützte Übersetzungen. Die Ursachen werden in `diagnostics` mit betroffenen IDs dokumentiert.

- Ein Attribut im falschen Container kann vollständig interpretiert sein.
- Ein eindeutig einer mitgelieferten Definition zugeordnetes Element einer weiteren Sprache kann ebenfalls vollständig interpretiert sein.
- Eine tatsächlich nicht auflösbare Definitionszuordnung oder nicht lesbare Struktur schränkt die Interpretation ein. Das Fehlen eines sprachspezifischen Adapters oder einer nicht erforderlichen Freitextgrammatik ist keine solche Lücke.
- Eine rein informative Beobachtung zu mehreren Sprachherkünften schränkt sie nicht allein deshalb ein.

Diagnosen zur Herkunft unterscheiden beispielsweise `AMBIGUOUS_LANGUAGE_ORIGIN`, `UNRESOLVED_LANGUAGE_ORIGIN`, `AMBIGUOUS_DEFINITION` und `UNRESOLVED_DEFINITION`. Die konkreten Codes werden bei der Umsetzung konsistent festgelegt; sie enthalten keine vorweggenommene fachliche Bewertung. Der Graph bewahrt in jedem Fall die belastbar bekannten Angaben. Ein unbekannter fachlicher Begriff im Label ist für sich genommen keine Parserdiagnose.

Gekürztes Beispiel eines eindeutig erkannten Elements aus einer weiteren Sprache:

```json
{
  "id": "erd-1",
  "kind": "element",
  "nativeType": "erd-entity",
  "label": "Kunde",
  "language": { "languageId": "language-erd", "versionId": "erd-version-1" },
  "languageResolution": "resolved",
  "definition": {
    "languageId": "language-erd",
    "versionId": "erd-version-1",
    "path": "/elements/0"
  },
  "definitionCandidates": [],
  "origin": { "cellIds": ["erd-1"], "derived": false }
}
```

Die Kennungen sind illustrativ; Vergleichstyp, Rolle und weitere Felder sind ausgelassen. Die Aussage ist ausschließlich „dieser Bestandteil stammt aus dieser ERD-Definition“. Ob ein solcher Bestandteil in der Aufgabe erlaubt oder fachlich richtig ist, wird daraus nicht abgeleitet.

### Kanten

| `kind` | Bedeutung | Erforderliche Informationen |
|---|---|---|
| `contains` | Unmittelbare Zugehörigkeit | `kind`, Besitzer als `source`, Kind als `target`, `directed: true`, `label: ""`, `language: null`, `type: content` oder `component` beziehungsweise `null` |
| `endpoint` | Ein Anschluss einer modellierten Beziehung | Beziehungsknoten, angeschlossenes Element, Endrolle, gegebenenfalls fachliche Portinformation und Herkunft |

**Alle modellierten Beziehungen werden als Beziehungsknoten ausgegeben.** Eine direkte fachliche Kante ist kein zweiter gleichzeitiger Repräsentationsweg. Die Quelle einer gerichteten Beziehung führt über eine `endpoint`-Kante zum Beziehungsknoten; dessen Zielanschluss führt zum Ziel. Diese technische Orientierung beschreibt die Inzidenz. Die fachliche Richtung steht am Beziehungsknoten.

`contains` hat keine zusätzliche ID, keine rekonstruierbare `origin`-Kopie und kein leeres `properties`-Objekt. Die Identität ergibt sich aus Art, Besitzer und Kind. `endpoint` behält dagegen ID, Anschlussherkunft und gegebenenfalls Portdaten. Technische Kanten werden nach Art, Quelle, Ziel und Typ sortiert; die Elementextraktion prüft diese Kombination auf Eindeutigkeit. Die Zusammenfassung trennt Elementknoten einschließlich verschachtelter Inhalte, modellierte Verbindungen, Zugehörigkeiten und technische Anschlüsse; sie errät keine sprachspezifischen Attributrollen.

Bei ungerichteten Beziehungen darf der spätere Vergleich die Enden zusammen mit ihren endbezogenen Eigenschaften vertauschen. Ein unbekannter Richtungswert wird nicht als ungerichtet interpretiert. Anschlusskoordinaten werden als Herkunft erhalten; fachliche Portrollen werden ausschließlich aus ausdrücklichen Angaben der mitgelieferten Definitionen übernommen.

### Gekürztes Beispiel

Der Ausschnitt zeigt die falsche Zugehörigkeit von `Menge`; weitere Knoten, Kanten und Metadaten sind ausgelassen:

```json
{
  "schema": "graph-result/v1",
  "evaluationId": "evaluation-1",
  "source": {
    "key": "submission",
    "role": "submission",
    "label": "Aktuelles Modell",
    "modelId": "model-s",
    "versionId": "version-s"
  },
  "graphHash": "sha256:student-graph",
  "graph": {
    "schemaVersion": 1,
    "nodes": [
      {
        "id": "s2",
        "kind": "element",
        "type": "container-type",
        "label": "Auftrag",
        "comparisonRole": "semantic",
        "origin": { "cellIds": ["s2"], "derived": false }
      },
      {
        "id": "s4",
        "kind": "element",
        "type": "detail-type",
        "label": "Menge",
        "comparisonRole": "semantic",
        "properties": { "dataType": "Integer" },
        "origin": { "cellIds": ["s4"], "derived": false }
      }
    ],
    "edges": [
      {
        "kind": "contains",
        "type": "content",
        "source": "s2",
        "target": "s4",
        "directed": true,
        "label": "",
        "language": null
      }
    ],
    "excluded": []
  },
  "completeness": { "interpretation": "complete" },
  "diagnostics": []
}
```

## Geplanter Arbeitsumfang

1. **Mitgelieferte Definitionen und Sprachherkunft allgemein auflösen.** Für jedes Element und jede modellierte Beziehung die vorhandenen Typangaben und die Herkunft anhand der zum Modell mitgelieferten Sprachdefinitionen erhalten. Keine Definition braucht eine zusätzliche sprachspezifische Mappingregel. Gleichnamige Typen verschiedener Sprachen oder Sprachversionen nicht ungeprüft gleichsetzen; die Identität über Sprach- und Definitionsbezug sichern. Mehrdeutige Definitionen und ihre ursprünglichen Kandidaten erhalten.
2. **Beziehungen vereinheitlichen.** Bereits vorhandene Beziehungsknoten beibehalten; einfache Verbindungen in dieselbe Form überführen. Original-ID, Label, Eigenschaften, Richtung und Anschlüsse erhalten. Kein doppeltes Auftreten als fachliche Kante und Beziehungsknoten.
3. **Vergleichsbereich begrenzen und Zugehörigkeiten rekursiv erhalten.** Zuerst ausschließlich den Inhalt des Modeling-Layers gemäß der vorstehenden Präzisierung auswählen. `contains` bildet darin die unmittelbare Modellstruktur ab. Technische Root-/Layer-Zellen sind keine Vergleichsbestandteile. Fachliche Container und Kindbestandteile bleiben sichtbar. Eine weitergehende strukturelle Rolle darf nur aus expliziten vorhandenen Daten hervorgehen, nicht aus bestimmten Typnamen, Beispielen oder vermuteten Fachbedeutungen. Der effektive fachliche Besitzer wird später durch Traversierung bestimmt; keine zweite persistierte Besitzerwahrheit erzeugen.
4. **Vorhandene Kindbestandteile und Attribute erhalten.** Bereits eigenständige Modellzellen bleiben eigenständige Knoten, gleichgültig ob ihre Sprache sie Attribute, Aktivitäten oder anders nennt. Vorhandene strukturierte Angaben werden allgemein übernommen. Freie Labels bleiben unverändert; keine Grammatik für Attributzeilen, Methoden, Sichtbarkeit oder andere sprachspezifische Inhalte entwickeln. Nicht zerlegter Freitext ist allein kein Parserfehler.
5. **Eigenschaftswerte ohne sprachspezifische Umdeutung erhalten.** Fehlend, leer und explizit gesetzt unterscheiden. Datentypen oder Konvertierungen nur aus tatsächlich vorhandenen eindeutigen Angaben ableiten. Keine Sonderfälle für Feldnamen wie `visibility`, keine Annahme, dass `?` allgemein unbekannt bedeutet, und keine eigene Kardinalitätsgrammatik. Unklare Werte unverändert erhalten.
6. **Darstellung abgrenzen.** Position, Farbe und Größe bestimmen keine fachliche Ähnlichkeit. Fachlich bedeutsame Reihenfolge oder Portrollen werden nur durch ausdrückliche Sprachregeln übernommen.
7. **Diagnosen und Vollständigkeit liefern.** Nicht oder mehrdeutig auflösbare Sprachen/Definitionen, unbekannte Typen, offene Enden, ungültige Besitzer und Zyklen innerhalb des Vergleichsbereichs kennzeichnen. Informative Beobachtungen von Interpretationslücken unterscheiden; keine fachliche Sprachbewertung oder Feedbackgenerierung im Parser ergänzen. Reguläre Infrastruktur und Feedback außerhalb des Vergleichsbereichs nicht einzeln inventarisieren oder als Interpretationslücke melden.
8. **Stabile Herkunft sicherstellen.** Erzeugte IDs basieren auf kollisionssicher kodierter Quellidentität und Transformationsrolle. Die Reihenfolge gewöhnlicher Modellzellen erzeugt keine andere ID; die Reihenfolge der direkten Wurzelkinder bestimmt gemäß Plattformkonvention den Vergleichsbereich. Abgabe und Referenz verwenden exakt dieselben Regeln.

Eigenständig definierte Inhalte bleiben unabhängig von vermuteten fachlichen Besitzertypen erkennbar, auch bei falscher Platzierung. Davon getrennt werden ausdrücklich deklarierte `children` und `additionalLabels` anhand ihrer Parent-Definition aufgelöst. Eine verbleibende Mehrdeutigkeit wird nicht durch eine willkürliche Auswahl beseitigt.

## Fehlerverhalten

- Kaputtes XML, doppelte Zell-IDs oder ein nicht unterstütztes Exportformat verhindern ein reguläres Graphartefakt.
- Eine fehlende oder beschädigte Canvas-/Layerstruktur verhindert ein reguläres Graphartefakt mit verständlichem Eingabefehler. Ein leeres XML-`root` ist kein gültiges leeres Modell.
- Ein vorhandener leerer Modeling-Layer in gültiger Plattformstruktur ergibt einen leeren Graphen mit `interpretation: complete` und ausschließlich informativem Bereichshinweis.
- Fehlende Endpunkte bleiben als offene Enden erhalten; ursprüngliche Ziel-IDs werden dokumentiert. Es werden keine erfundenen Fachknoten ergänzt.
- Fachliche Zugehörigkeitszyklen bleiben als Problemstruktur erhalten. Nachfolgende Traversierung muss den betroffenen Bereich begrenzen können.
- Eine tatsächlich fehlende oder mehrdeutige Definition ergibt eine lokalisierte Diagnose und gegebenenfalls `interpretation: partial`. Freie Labeltexte müssen nicht sprachspezifisch zerlegbar sein und werden nicht deshalb als unvollständig interpretiert markiert.
- Ein eindeutig erkanntes Element einer weiteren Modellierungssprache ist allein deshalb weder ein technischer Fehler noch ein Interpretationsfehler. Es bleibt mit seiner tatsächlichen Herkunft erhalten; es braucht keine zusätzliche Profilunterstützung.
- Ein ungültiger Referenzgraph ist keine korrekte Musterlösung nur deshalb, weil sein XML parsebar ist. Seine Diagnosen werden bis zur Referenzauswahl weitergereicht.

## Erfüllungskriterien

**Modeling-Layer-Abgrenzung – implementiert und statisch durchgesehen, nicht zur Laufzeit verifiziert:**

- [x] Ausschließlich der rekursive Inhalt des Modeling-Layers erzeugt Vergleichsknoten; Canvas-Wurzel und Layer erzeugen weder Knoten noch Zugehörigkeitskanten.
- [x] Fachliche Container und unbekannte Bestandteile innerhalb dieses Bereichs bleiben erhalten; Abgabe und Referenz verwenden dieselbe Auswahlregel.
- [x] Feedback, andere Layer und Verbindungen zu ausgeschlossenen Bestandteilen gelangen einschließlich ihrer zugehörigen Beschriftungen nicht in den Vergleich.
- [x] Reguläre Bereichsausschlüsse erzeugen keine ausführlichen Einzeleinträge oder Warnungen; vorhandene offene Enden und Interpretationslücken bleiben unterscheidbar.
- [x] Fehlende beziehungsweise beschädigte Layerstruktur und ein gültiger leerer Modeling-Layer werden unterschiedlich behandelt.
- [x] Elementinventar und Synonym-Matching verwenden die begrenzte Elementmenge ohne erneute XML-Auswahl; V1-Verträge bleiben erhalten.

**Offene Grenzen:** Die bestehende Plattformreihenfolge muss im Snapshot erhalten sein. Ein Vertauschen zweier ansonsten gleich strukturierter Layer ist ohne zusätzliche Kennzeichnung nicht erkennbar; es werden dafür keine Label-/Typheuristiken oder neuen Metadaten eingeführt. Zellen ohne Elternpfad zum Modeling-Layer liegen außerhalb des Vergleichs, auch bei beschädigten fachlichen Elternreferenzen. Die allgemeine Definitionsauflösung und echte offene Enden bleiben diagnostizierbar. Die reine Layer-Abgrenzung benötigte keine zusätzliche Ausschlusslogik in den Verbrauchern. Für die anschließenden kompakten Verträge wurden Inventarerzeuger und Synonym-Service dagegen gemeinsam angepasst. Der strukturelle Matcher bleibt ein Platzhalter. Laufzeitfunktion und reale aufgabenübergreifende Ergebnisse bleiben bis zu einem gesonderten Prüfauftrag offen. Beschriftungsaufbereitung, Methoden, Gewichte und Kandidatenmenge sind unverändert; die Ausgabe enthält weniger Datenkopien.

**Statisch durchgesehen:** Die folgenden Häkchen beschreiben den implementierten Vertrag. Sie sind kein Laufzeitnachweis der allgemeinen Verarbeitung.

- [x] Alle Aufgaben und Sample Solutions im vorhandenen Modellformat verwenden denselben allgemeinen Parserpfad anhand ihrer mitgelieferten Definitionen.
- [x] Keine feste Sprache, Beispieldefinition, Ressourcenhash-Ausnahme, kanonische Typ-Mappingliste oder sprachspezifische Textgrammatik ist erforderlich.
- [x] `comparisonConfig: {}` reicht für die allgemeine Strukturüberführung; eine erkannte Definition wird nicht nur wegen einer fehlenden Mappingregel als `unsupported` behandelt.

- [x] Das gleiche Modell erhält als Abgabe und als Referenz dieselbe fachliche Struktur.
- [x] Jede modellierte Beziehung besitzt genau eine fachliche Identität, unabhängig von Kindern oder Einbettung.
- [x] Mehrstufige Zugehörigkeiten und falsche Besitzer bleiben im Graphen erkennbar.
- [x] Jedes relevante Originalelement oder erzeugte Attribut ist auf seine Quelle zurückführbar.
- [x] Elemente und modellierte Beziehungen behalten ihre eindeutig bekannte Modellierungssprache und Sprachversion; mehrdeutige und fehlende Zuordnungen sind davon unterscheidbar.
- [x] Eine bekannte weitere Sprache bleibt erkennbar und wird nicht pauschal als unbekannt, unvollständig oder fachlich falsch eingestuft.
- [x] Mitgelieferte Sprachdefinitionen, tatsächlich verwendete Sprachen und technische Strukturkanten werden nicht miteinander verwechselt.
- [x] Der optionale Prüfpunkt zu mehreren beziehungsweise aufgabenbezogen anderen Sprachherkünften ist beurteilt; eine gegebenenfalls eingeführte Diagnose bleibt neutral und erzeugt kein Feedback.
- [x] Layout und technische Anschlusskanten erzeugen keine zusätzlichen fachlichen Modellbestandteile.
- [x] Unbekannte und fehlerhafte Bestandteile innerhalb des Vergleichsbereichs verschwinden nicht; Vollständigkeit und Diagnosen passen zum Inhalt.

**Aktuelle Verifikation:** Ausschließlich statische Durchsicht der Änderungen und ihrer Schnittstellen. Keine Beispiele ausführen, keine Modellpaare parsen, keine Container starten und keine Tests, Builds, Lint- oder Syntaxprüfungen anlegen oder ausführen. Allgemeine Laufzeitfunktion ist bis zu einem gesonderten Prüfauftrag ausdrücklich ungetestet.

**Herkunftsvertrag der Umsetzung:** Jeder Originalknoten trägt `origin.cellIds`, die ursprünglichen XML-Attribute, unveränderte skalare Eigenschaften und den Transformationsbezug. `endpoint` erhält Anschlussherkunft; die Herkunft einer `contains`-Kante ist aus Quelle, Ziel und allgemeiner Erzeugungsregel rekonstruierbar und wird nicht zusätzlich gespeichert. `languageResources` enthält die mitgelieferten Definitionsstände samt Inhaltshash; `producer.resourceHash` bindet die allgemeine Verarbeitung an ihre tatsächlichen Quelldateien. `graphHash` umfasst Quelle, diese beiden Herkunftsbereiche, Graph, Vollständigkeit und Diagnosen. Die Hashes dienen nicht zur Freischaltung von Definitionen. Es wird kein Profilhash eingeführt. Die direkten Verbraucher sind ausschließlich auf Graph-V1 abgestimmt; ihre Folgepakete bleiben offen.

**Prüfgrenze:** Frühere Probeläufe während der Entwicklung bezogen sich auf einen inzwischen entfernten sprachspezifischen Zwischenstand. Sie belegen den abschließenden generischen Stand nicht. Seit der Korrektur des Arbeitsrahmens wurden keine weiteren Laufzeit-, Syntax- oder Testprüfungen ausgeführt.

**Übergabe:** [03 – Elementinventar](03-model-label-extraction.md) liest den Graphen; [05 – One-to-One](05-one-to-one-graph-matching.md) verwendet später genau dasselbe Artefakt.
