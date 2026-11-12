# synonym-matching

Erzeugt für genau ein Abgabe-/Referenzpaar vollständige semantische Kandidatenevidenz.
Der Service verarbeitet ausschließlich die V2-Inventare aus Paket 03. Er liest kein
Modell-XML und vergibt keine IDs. Die Implementierung und Capability heißen
`synonym-matching`, Serviceversion `0.1.0`.

**Stand:** An die lokale Auswertungspipeline bis Phase 4 angebunden. Ein eigener
Paarlauf verarbeitet jede Musterlösung gegen das einmal erzeugte Abgabeinventar;
das Kandidatenartefakt ist in der Auswertungs-Sidebar verfügbar. Der ursprüngliche
Implementierungsauftrag war rein statisch; die anschließende Integration umfasst
auf ausdrücklichen Auftrag auch Image-Build und gezielte Laufzeitverifikation.
Strukturelles Matching, Feedback und Bewertung sind nicht enthalten.

## Eigener Code und Methodenherkunft

`synonym-matching-louis` dient ausschließlich als lesbare Methodenreferenz.
Weder Runtime-Importe noch Docker-COPY, Quellcode-Mounts oder das Referenzimage
werden benötigt. Der Zielcontainer kopiert nur seinen eigenen Servicecode und
das gemeinsame `workflow_io.py` aus `dagu/workflow-services`.

| Datei unter `src/synonym_matching/` | Verantwortung und Übernahmegrundlage |
|---|---|
| `methods/levenshtein.py` | RapidFuzz `Levenshtein.normalized_similarity`, aus der Referenz übernommen |
| `methods/jaro_winkler.py` | RapidFuzz `JaroWinkler.normalized_similarity`, gleiche Standardparameter |
| `methods/char_trigram.py` | Jaccard über Zeichen-Trigrammmengen; Texte mit weniger als drei Zeichen bilden wie in der Referenz ein einzelnes Gramm |
| `methods/multilingual.py` | Referenzmodell, normierte Embeddings und Cosinus; Textmerkmale einmal pro verschiedenem Text, eigene Offline-Ressourcenprüfung |
| `methods/pairwise.py` | Gemeinsame Paariteration der Stringverfahren |
| `methods/registry.py` | Kleine explizite Registry mit Scorebereich, Berechnung, Vorverarbeitung, Parametern und optionaler Ressourceninitialisierung |
| `preprocessing.py` | Aus der Referenz übernommenes NFC und Zusammenfassen von Whitespace |
| `config.py` | Validierung der aktivierten Methoden und Vorverarbeitung |
| `service.py` | Genau ein Paar, Einzelmatrizen, Kandidaten, unveränderte Instanzdaten |
| `inventories.py` | V2-Schema, Identitäten, Inventarhashes und Snapshot-Bindung prüfen |
| `provenance.py` | Kanonische Hashes, eigene Codekennung und verwendete Paketversionen |
| `workflow.py` | Workspace-Eingabe, Diagnosen und V1-Ergebnishülle |

`src/main.py` liest CLI-Optionen, ruft den Ablauf auf und veröffentlicht das fertige
Ergebnis über `workflow_io`. Es gibt kein Plugin-Framework. Forschungsrunner,
Testinfrastruktur, Übersetzungsmodelle, Lexika und unbenötigte Methoden wurden
nicht übernommen.

Die Übernahmegrundlage ist mit folgenden Git-Blobkennungen des wiederhergestellten
Referenzstands nachvollziehbar; der laufende Service liest diese Dateien nicht:

| Referenzdatei unter `src/synonym_matching/` | Git-Blob |
|---|---|
| `methods.py` | `b61a46423065dfed8436e0f25e51a9c0f5a0600f` |
| `preprocessing.py` | `f3f9f00d3dd78c4d71477c7210827faf93fb96f3` |
| `config.py` | `51b0d734bec8dfe159b2ac611aa2ddc4c650afee` |

## Workspace-Eingabe

Alle Artefaktpfade sind relativ zu
`<WORKFLOW_DATA_ROOT>/<WORKFLOW_EVALUATION_ID>/`; der bestehende Standard für
`WORKFLOW_DATA_ROOT` ist `/work/evaluations`.

| Eingang | Vertrag |
|---|---|
| `WORKFLOW_EVALUATION_ID` | Gültige Auswertungs-ID; aktiviert den Workspace-Modus |
| `REFERENCE_KEY` | Genau eine Referenz mit Rolle `reference` aus dem eingefrorenen Snapshot |
| `inputs/evaluation-input.json` | Bestehender Snapshot `evaluation-input/v1`; Zugriff und `inputHash` werden durch `Workspace.snapshot()` geprüft |
| `labels/submission.json` | Vollständige erfolgreiche `workflow-result/v1`-Hülle mit `result.schema: element-inventory/v2` |
| `labels/<REFERENCE_KEY>.json` | Dieselbe Inventarhülle für die gewählte Referenz |
| `comparisonConfig` | Aus dem Snapshot; `{}` genügt |
| `WORKFLOW_OUTPUT_PATH` | Erforderlich, regulär `candidates/<REFERENCE_KEY>.json`; Dateiname muss zur Referenz passen, Verzeichnispräfix ist innerhalb des Workspace frei |

Inventare müssen dieselbe `evaluationId` und denselben `inputHash` besitzen.
Vollständige Quellen werden mit dem Snapshot abgeglichen. Beide `inventoryHash`-
Werte werden über den gesamten jeweiligen Inventarinhalt ohne eigenes Hashfeld
nachgerechnet. `graphHash`, Parserkennung, Sprachressourcen, Ausschlüsse,
Interpretationsstatus, Diagnosen und alle Elemente bleiben erhalten. Die Graphdatei
wird nicht erneut gelesen; Paket 05 muss die mitgelieferten Graphhashes mit seinen
Graphen abgleichen.

`WORKFLOW_INPUT_PATH`, `TEMPLATE_INPUT` und `--input` werden im Workspace-Modus
abgelehnt: Das Paar stammt ausschließlich aus den beiden benannten Inventardateien.
Damit kann keine alternative Eingabe die eingefrorene Konfiguration überschreiben.

## Eigenständige Eingabe

Ohne `WORKFLOW_EVALUATION_ID` ist der Eingang ein JSON-Objekt mit genau diesen
Feldern, beschrieben in `schemas/input.schema.json`:

| Feld | Inhalt |
|---|---|
| `studentInventory` | Vollständige erfolgreiche Inventarhülle für `source.key: submission`, `source.role: submission` |
| `referenceInventory` | Genau eine vollständige erfolgreiche Inventarhülle mit `source.role: reference` |
| `comparisonConfig` | Optionales Objekt, Standard `{}` |

Lesen erfolgt über `--input`, alternativ `TEMPLATE_INPUT` oder stdin; Schreiben
über stdout oder `--output`. Workspace-Umgebungsvariablen benötigen die Auswertungs-ID.
Die gegenseitige Lauf-, Quellen- und Hashkonsistenz wird auch eigenständig geprüft;
ohne Workspace gibt es keinen Abgleich mit einem externen Snapshot.
Die frühere Demo-/Graph-Eingabe ist durch den Inventarvertrag ersetzt.

## Konfiguration, Texte und Skalen

`comparisonConfig: {}` bleibt ausreichend. Optional kann
`comparisonConfig.semantics.methods` eine nicht leere Liste eindeutiger,
registrierter Namen enthalten; ohne diese Liste werden alle vier Standardmethoden
aktiviert. `semantics.preprocessing` kann die Standardvorverarbeitung `normalize`
mit einer Liste registrierter Schritte überschreiben. Unbekannte oder doppelte
Methoden/Schritte werden als Konfigurationsfehler zurückgewiesen.

Jede Methode liefert ausschließlich ihren eigenen Score:

- Levenshtein, Jaro-Winkler und Zeichen-Trigramme: Rohscores in `[0,1]`.
- Multilinguales Embedding: Cosinus-Rohscores in `[-1,1]`.
- Es gibt weder Gewichtung noch kombinierten Score oder finale Zuordnung.
- Scores werden nicht gerundet und nicht als Wahrscheinlichkeiten interpretiert.

Alle Berechnungen verwenden ausschließlich `matchText`, gefolgt von der
konfigurierten Vorverarbeitung (standardmäßig NFC und Zusammenfassen von Whitespace).
Originallabel, ursprünglicher Vergleichstext,
natürliche `textLanguage` und Modellsprachreferenzen bleiben getrennt erhalten.
Es gibt kein Lowercasing, keine Übersetzung, keine Sprachschätzung und keine
sprachspezifische Sonderbehandlung. Das multilinguale Verfahren benötigt keine
explizite natürliche Sprache; aus `language` wird keine solche abgeleitet.
Normalisierte gleiche Texte werden je Methodengruppe einmal berechnet; Element-
und Verbindungstextinstanzen bleiben getrennt. Das Embedding-Modell und seine
Textvektoren werden pro Serviceaufruf wiederverwendet.

`labelStatus: missing` beziehungsweise `unsupported` kennzeichnet nicht auswertbare
Texte. Diese Instanzen bleiben im vollständigen Inventar und unter
`unscoredElements` mit `missing_text` beziehungsweise `unsupported_text` erhalten.
Jede Referenzinstanz erhält eine Matrixzeile, gegebenenfalls mit `matches: []`.
Gleiche Texte mit verschiedenen IDs bleiben getrennte Kandidateninstanzen.
Vor dem Scoring werden nur Paare mit identischer Sprach-ID und Sprachversion
zugelassen. Bei zwei gesetzten Vergleichsgruppen müssen diese übereinstimmen;
sind beide Gruppen nicht gesetzt, müssen die konkreten Typen übereinstimmen.
Gemischte Gruppierung, inkompatible Sprachen und unterschiedliche Gruppen sind
keine Kandidaten. Es gibt weder Top-k noch Threshold-Filterung oder endgültige
Zuordnung. Ein zulässiges Paar bleibt auch ohne Beschriftung erhalten und wird
mit `scoreStatus: unavailable`, einem Grund und `scores: null` ausgewiesen.
Verbindungstexte werden nur bei auswertbarem Text und übereinstimmender Art
verglichen; zusätzliche Labels benötigen zusätzlich dieselbe nicht leere
`connectionLabelId`. Unbeschriftete Verbindungen erzeugen keine Textpaare.

## Ausgabe und Herkunft

Die Ausgabe ist eine `workflow-result/v1`-Hülle mit `schemaVersion: 1`, `status: ok`,
`capability: synonym-matching`, `mode: match` und `result.schema: semantic-candidates/v1`.
`schemas/output.schema.json` beschreibt die Ausgabe; `input.schema.json` definiert
`element-inventory/v2` mit Typ-, Vergleichsgruppen- und Sprachfeldern sowie
gesonderten Verbindungstexten. Für die fachlichen Elemente nutzt das Matching
`id`, `type`, `comparisonGroup`, `language`, `matchText` und `labelStatus`.
Eigenständige Aufrufer bewahren die Inventare unter
`labels/<modelKey>.json` sowie die darin referenzierten Graphen separat auf.

| Feld in `result` | Inhalt |
|---|---|
| `evaluationId`, `inputHash`, `pair` | Lauf, Snapshot und genau ein Paar von Modellschlüsseln |
| `graphHashes`, `inventoryHashes` | Unveränderte Bindungen jeweils unter `student` und `reference` |
| `inventoryPaths` | Relative Eingabepfade `labels/<modelKey>.json` unter `student` und `reference`; Inventare und Originalgraphen bleiben separate Artefakte desselben Laufs |
| `semanticConfig`, `semanticConfigHash` | Aktivierte Methoden und Vorverarbeitung samt Hash |
| `producer` | Serviceversion, eigener Code-/Schemahash, Python-/Unicode- und verwendete Paketversionen |
| `methods` | Nur aktivierte Verfahren mit Scorebereich, Vorverarbeitung, Parametern und optionalen Ressourcenmetadaten |
| `candidatePairCount`, `scoredPairCount`, `unavailablePairCount` | Zahl zulässiger Paare und deren Scoring-Verfügbarkeit |
| `processedTexts` | Tatsächlich verwendeter Text einmal pro vorhandener fachlicher oder Verbindungsbeschriftungs-ID |
| `synonymMatrix` | Nur zulässige Kandidaten; `referenceLabel` und `submissionLabel` geben den jeweiligen `matchText` unverändert wieder, während IDs die technischen Identifikatoren bleiben. `comparisonBasis` und `scoreStatus` erklären die Paarbildung; `scores` enthält aktivierte Methoden oder ist bei fehlendem Text `null` |
| `connectionTextMatrix` | Flache Liste tatsächlich bewerteter Textpaare mit Owner-IDs, `referenceLabel` und `submissionLabel` aus den Inventaren, Beschriftungsart/-slot und unabhängigen Methodenscores; ohne kompatible Texte `[]` |
| `unscoredElements` | Seite, ID und Grund für jede Instanz ohne verwendbaren Text; Modellbezug ergibt sich aus `pair` |
| `completeness`, `diagnostics` | Technisch vollständig bei Erfolg; Interpretation berücksichtigt Inventare und nicht bewertbare Verbindungstext-Paare, Diagnosen weisen die Einschränkung explizit aus |
| `candidateHash` | Hash des vollständigen `result` ohne dieses eigene Hashfeld |

Eigene Hashes verwenden SHA-256 als 64-stelligen Hexstring ohne Präfix über
kanonisches UTF-8-JSON, sortierte Objektschlüssel, keine zusätzlichen Leerzeichen,
keine ASCII-Escapes und keine Zeitstempel. Inventare bleiben separat gespeichert;
eigene Instanzlisten und Kandidaten werden stabil nach IDs geordnet. Vorhandene fachlich geordnete Listen behalten ihre
Reihenfolge. `producer.resourceHash` umfasst eigenen Python-Code, beide Schemata
und das tatsächlich importierte gemeinsame `workflow_io.py`.

## Ressourcen und Fehler

Verwendet wird ausschließlich das bereits gewählte Modell
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` an Revision
`e8f8c211226b894fcb81acc59f3b34ba3efd5f42`, CPU, Batchgröße 32 und normierte Embeddings.
Der Ressourcenbericht hält angeforderte und aufgelöste Revision sowie das
Modell-Tokenlimit fest. Ohne verwendbares Textpaar wird kein Modell geladen;
`resolvedRevision` und Tokenlimit bleiben `null`, Status ist
`not_needed_no_usable_pairs`. Das ist eine gültige leere Evidenz, kein Ersatzscore.

Der Docker-Buildkontext ist `dagu/workflow-services`, Dockerfile ist
`synonym-matching/Dockerfile`. Eigene Anforderungen übernehmen nur die für den
Standard nötigen Bibliotheken und Versionen aus der Referenz. Der Build bereitet
über `scripts/prepare_model.py` ausschließlich dieses Modell vor. Der Aufruf pro
Paar arbeitet offline mit `local_files_only=True`; fehlendes `modules.json`
verhindert zusätzlich den automatischen Wechsel auf eine andere Pooling-Pipeline.
Der lokale Image-Build für die Phase-4-Integration bereitet diese Modellressource vor.

Ungültige Inventare, doppelte IDs, falsche Quellen, Hashabweichungen, ungültige
Methodenwerte, fehlende Ressourcen, Methodenausfälle oder Überschreitung des
Modell-Tokenlimits führen zu Exitcode 1 und stderr. Es wird dann kein neues
Erfolgsartefakt veröffentlicht, keine Methode ersetzt und kein Gewicht verändert.
Workspace-Publikation ist atomar und unveränderlich: identische Wiederholungen
sind erlaubt; abweichender Inhalt am selben Pfad ergibt einen Konflikt.

Ein numerisches Paarlimit ist bislang nicht vereinbart und wird hier nicht
erfunden. Die Matrix wächst vollständig mit dem Produkt der Inventargrößen;
Speicherfehler werden als technische Fehler weitergegeben. Konkrete Betriebsgrenzen
bleiben bei zusätzlichem Bedarf festzulegen. Der Hauptworkflow begrenzt die
Paarparallelität zunächst auf einen Lauf und weist diesem 2 GiB Speicher zu.
Ein technischer Integrationslauf ist kein Nachweis kalibrierter semantischer
Qualität auf realen Abgaben.
