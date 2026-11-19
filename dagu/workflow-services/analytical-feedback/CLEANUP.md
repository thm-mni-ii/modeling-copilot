# Graph-Evaluation: Cleanup-Nachweis

Aktueller Nachtrag vom 15.11.2026: Die feste Kategorieeinteilung ist durch
referenzbasierte Gruppen-/Typzeilen ersetzt. Vorhandene Vergleichsgruppen werden
zusammengefasst; alle nicht gruppierten Typen werden separat gezaehlt. Es erscheinen
nur Zeilen mit mindestens einem Referenzobjekt. Keine neuen Kategoriemetadaten,
Sprachversionen oder Migrationen erforderlich. Der Kategorieeditor und die
API-Erzeugung eingefrorener `elementCategories` sind entfernt. Historische
Migrationen bleiben unveraendert. Die folgenden v2-Groessenmessungen dokumentieren
den vorherigen Cleanup und sind keine Messung des neuen v3-Ausgabeformats.

Aktueller Vertrag: `analysis-feedback/v3`, `feedback-report/v3`; beide Dienste
Version 2.1.0, Images v8, Hauptworkflow v8. Der Matcher bleibt unveraendert auf v4.
20 betroffene Analyse-/Vertragstests und 11 API-Tests bestehen; darunter Gruppen,
Referenznenner, nicht gruppierte Typen, Scope der Gruppen und Datenschutz.
Vue/TypeScript-Typpruefung und gezieltes Lint erfolgreich; bestehende v1-/v2-Analysen
bleiben lesbar. Dagu-MCP-Preview gueltig, lokale API erneuert. Beide v8-Images
sind gebaut und mit identischen Digests im Executor importiert:
Analyse `sha256:dbebc87e2122c0e2041fbed3a812d7067ad74adbf23e6d9416d4687001a1b1e9`,
Feedback `sha256:7d9d97fecc426bf6f5086ca1d23a90df484b239564c91a179ec5e4733b642435`.
Keine Workflow- oder Kubernetes-Jobs gestartet.



Stand: 14.11.2026. Keine Zuordnungsheuristiken, Schwellen oder Synonymverfahren geändert.

## Entfernte Altlasten und Zuständigkeit

- Aufrufstellen und Tests vor Entfernung geprüft: Analytical Feedback importierte das komplette Feedback-Generation-Modul und erzeugte einen ungenutzten Zwischenbericht. Dieser Aufruf und die Docker-Abhängigkeit sind entfernt.
- Der alte heuristische Analysewriter und die parallele Aggregation vorläufiger Matcher-Zahlen in Feedback Generation sind entfernt. Nur Leser für gespeicherte Analysevertraege bleiben erhalten; `legacy_category_summary` dient ausschließlich deren Validierung.
- Der Matcher entscheidet Zuordnungen, Identität und Eigenschaften. Analytical Feedback projiziert ausgewaehlte Fakten und berechnet `recognition`. Feedback Generation validiert und veröffentlicht diese Übersicht unveraendert. Die UI validiert und zeigt veröffentlichte Zahlen an.
- Regul?re Vergleichsartefakte speichern keine unselektierten Identitätskandidaten, Entscheidungslogs oder vorläufigen Diagnosemetriken. Diese sind mit `GRAPH_MATCHING_DIAGNOSTICS=1` unter `diagnostics` verfuegbar. Berechnungsrelevante Evidenzen bleiben erhalten.
- Analytical Feedback enthaelt kompakte Einzel- und Gruppenfakten statt vollständiger Rohkopien, mehrfacher Identitätskriterien und redundanter `match`/`checks`/`consistency`-Gesamtstatus. Dieselbe Positionsabweichung hat eine gemeinsame Finding-ID.

## Verträge, Kategorien und Rollen

`reference-comparison/v2`, `analysis-feedback/v2` und `feedback-report/v2` versionieren die inkompatiblen Änderungen. Das `workflow-result/v1`-Envelope und vollständige kompakte JSON-Zeilen auf stdout bleiben erhalten. Schema und Statusdefinitionen liegen beim bestehenden Analysevertrag; Feedback Generation hat keine zweite fachliche Zähllogik.

Erkannt sind ausschließlich ausgewaehlte eindeutige 1:1-Identitäten mit hinreichender nicht zirkulaerer Evidenz. Unterstützung oder Typkompatibilitaet allein zaehlt nicht. Die vier Kategorien und die Gesamtsumme verwenden `recognized`, `expected`, `percent`, `evaluationStatus`; nicht zugeordnete Abgabeobjekte stehen separat. Ohne Auswertbarkeit bleibt Prozent null. Strukturelle Container bleiben außerhalb fachlicher Nenner.

Kategorien können in neuen Sprachdefinitionen deklariert werden, werden durch das API-Schema validiert und anhand der gepinnten Sprachversion im Evaluationssnapshot eingefroren. Historische Migrationen und ihre Sprachdateien bleiben unverändert. Die zunächst vorgenommenen Ergänzungen an fünf historischen Sprachdateien wurden zurückgenommen. Laufzeitcode verwendet keine sprachspezifischen Typnamen. Bestehende produktive Releases ohne Kategorien benötigen eine gesondert geplante neue Sprachversion oder Datenmigration; diese Überführung wurde nicht umgesetzt oder ausgeführt.

API und Frontend lesen weiterhin gespeicherte Analyse-v1-Revisionen ohne contractVersion sowie 1.1, 1.2 und 1.3. Der alte Generierungsweg ist entfernt; neue v2-Berichte benötigen aktuelle Matcher-Fakten. Alte Feedback-v1-Berichte werden als historische technische Ergebnisse erhalten und nicht zu aktuellen Erkennungsquoten umgedeutet.

Übersicht und Analysedetails teilen die Referenzauswahl. Workflowfortschritt, Erkennung und Note bleiben getrennt. Positive Fakten, Abweichungen und offene Prüfungen sind parallel sichtbar; ausfuehrliche Diagnosen sind optional. Studierende erhalten nur aggregierte Erkennung und eigene offene IDs; Referenzfakten, Namen, Rohgraphen, Kandidaten und Logs bleiben geschützt. API-Filter greifen vor dem Abruf geschützter Zwischenergebnisse.

## Lokale Verifikation

- 147 betroffene Matcher-Tests bestanden, darunter vorhandene Identitäts-, Richtungs-/Typ-, Parallelverbindungs-, Struktur- und Zyklusfaelle. Der Diagnoseschalter veraendert Mapping und Fakten nicht.
- 18 Analyse-/Vertragstests bestanden: Projektion, Parent mit korrekten/fehlenden/zusätzlichen/verschobenen Kindern, Original-IDs, Zieladressen, doppelte Zuordnungen, nur unterstützte Identitäten, leere/nicht/teilweise auswertbare Kategorien, Kategorie des Referenzobjekts und gespeicherte Modelle.
- 10 API-Tests bestanden: Kategorien, Lesbarkeit unveränderter historischer Sprachdefinitionen, gepinnter Snapshot statt Caller-Override, Rollen und studentische Datenfilter. Nach der Korrektur wurden die sieben betroffenen Kategorieprüfungen und die gespeicherten Modellfälle erneut erfolgreich geprüft.
- JSON-Schema und tatsächlicher TypeScript-Adapter mit installiertem AJV/TypeScript geprüft; vier gespeicherte Altvertragsrevisionen bleiben lesbar. Ein realer lokaler Dienstaufruf prüft Analyse-stdout, Feedback-Generation, veröffentlichte Gleichheit und Frontendadapter zusammen.
- Lint für sieben betroffene Frontenddateien sowie Vue/TypeScript-Typpruefung erfolgreich. Keine Browserautomation, vollständige Kubernetes-Pipeline, Embeddingberechnung oder Synonym-Matching-Laeufe.

Die kleinen generischen Fixtures und gespeicherten Modell-Snapshots verwenden vollständige kompatible Kandidaten ohne neue semantische Scores. Es handelt sich nicht um die historischen, eingefrorenen Evaluations-/Kandidatenketten. Die Vorher-/Nachher-Größenmessung verwendet identische eingefrorene lokale Eingaben ohne neue Kategoriemetadaten. Jede ausgewaehlte Zuordnung und jeder urspruengliche vollständige Matcher-Fakt blieb gleich; beim Faktenvergleich wurden nur Fakt-ID und die neue Auswertbarkeitsangabe ausgeblendet. Die IDs selbst ändern sich inhaltsbedingt durch die ergänzte Auswertbarkeit.

Mit den unveränderten historischen Sprachdefinitionen ergeben dieselben gespeicherten Modelle:

| Modell | Knoten | Attribute | Verbindungen | Other | Insgesamt | Quote | Ohne Zuordnung |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| M02 | 0/0 | 0/0 | 10/10 | 46/48 | 56/58 | 96,55 % | 2 |
| M04 | 0/0 | 0/0 | 8/10 | 42/48 | 50/58 | 86,21 % | 1 |
| M08 | 0/0 | 0/0 | 8/10 | 47/48 | 55/58 | 94,83 % | 2 |

Die identische Baseline erreicht 58/58. Ohne deklarierte Kategorien bleiben die fachlichen Elemente dieser historischen Sprachdefinitionen unter `other`; Knoten und Attribute haben hier Prozent null. Neue Kategoriendeklarationen werden mit getrennten generischen Testdaten geprüft. Die zuvor berichtete Aufteilung in Knoten und Attribute war eine lokale Simulation mit ergänzten Metadaten und beschreibt keinen produktiven Datenstand.

## JSON-Größen

Vollständige Envelopes, kompaktes JSON in UTF-8, Bytes; keine Kompression. Links/rechts: vorher/nachher.

| Modell | Graphvergleich | Analytical Feedback | Feedback Generation |
| --- | ---: | ---: | ---: |
| M02 | 3.029.965 / 450.846 | 580.784 / 303.463 | 57.451 / 1.596 |
| M04 | 2.679.071 / 410.944 | 524.744 / 274.247 | 54.744 / 1.561 |
| M08 | 2.982.714 / 450.926 | 591.204 / 307.330 | 58.088 / 1.665 |

Reduktion: Graphvergleich 84,7-85,1 %, Analyse 47,7-48,0 %, Feedback 97,1-97,2 %. Keine positiven Einzelbeweise für diese Einsparung entfernt.

## Lokale Bereitstellung

Alle drei Dienste: Serviceversion 2.0.0; Hauptworkflow v7, interner Matcher v4, Analyse-/Feedback-Unterworkflow v7. MCP-Preview der bestehenden Dagu-Instanz: gültig, keine Fehler. Die YAML-Datei bleibt wie bisher lokal eingebunden.

| Image | Identischer Docker-/Executor-Digest |
| --- | --- |
| `one-to-one-graph-matching:v4` | `sha256:377cc4fb5c515657626be96dbf8f1a401f4ab13719d2df3d3b9a2018d21b756f` |
| `analytical-feedback:v7` | `sha256:d73b8fa0c05e3c6c5024dc8041dfa2a83cc6ea4c5b622136bae36706086cde03` |
| `feedback-generation:v7` | `sha256:1586e63a721d23489de1e00dd31048f8460d69d468024b4770afbe908f77177e` |

Images gebaut und in den vorhandenen Docker-Desktop-Kubernetes-Image-Speicher importiert. API separat gebaut und erneuert; Anwendungsstart erfolgreich. Keine Kubernetes-Jobs gestartet, kein Datenbankreset oder Backfill ausgeführt.

## Fachliche Grenzen außerhalb des Cleanups

- Globale Modellkorrektheit und Notengebung bleiben nicht implementiert; `assessmentAvailable` bleibt false.
- Symmetrische oder nur teilweise strukturell gestützte Objekte können weiter offen bleiben. Dieser Cleanup ergänzt keine Identitätsheuristik.
- Ein Defizit paralleler Verbindungen beweist keine bestimmte fehlende Einzelverbindung. Offene Gegenstuecke bleiben von nachgewiesener Abwesenheit getrennt.
- Bestehende Releases/Snapshots ohne Kategorien werden nicht nachträglich umklassifiziert. Historische Pipelinekennzahlen wurden nicht rekonstruiert.

## Tatsächlich geänderte Dateien

- [api/src/modeling_api/schemas/languages.py](../../../api/src/modeling_api/schemas/languages.py)
- [api/src/modeling_api/services/evaluations.py](../../../api/src/modeling_api/services/evaluations.py)
- [api/tests/test_evaluation_categories.py](../../../api/tests/test_evaluation_categories.py)
- [api/tests/test_evaluation_visibility.py](../../../api/tests/test_evaluation_visibility.py)
- [dagu/README.md](../../README.md)
- [dagu/workflow-services/analytical-feedback/CLEANUP.md](CLEANUP.md)
- [dagu/workflow-services/analytical-feedback/Dockerfile](Dockerfile)
- [dagu/workflow-services/analytical-feedback/README.md](README.md)
- [dagu/workflow-services/analytical-feedback/schemas/output.schema.json](schemas/output.schema.json)
- [dagu/workflow-services/analytical-feedback/src/analysis.py](src/analysis.py)
- [dagu/workflow-services/analytical-feedback/src/analysis_contract.py](src/analysis_contract.py)
- [dagu/workflow-services/analytical-feedback/src/fact_projection.py](src/fact_projection.py)
- [dagu/workflow-services/analytical-feedback/src/main.py](src/main.py)
- [dagu/workflow-services/analytical-feedback/tests/fixtures/legacy-analysis.json](tests/fixtures/legacy-analysis.json)
- [dagu/workflow-services/analytical-feedback/tests/test_analysis.py](tests/test_analysis.py)
- [dagu/workflow-services/analytical-feedback/tests/test_contract.py](tests/test_contract.py)
- [dagu/workflow-services/analytical-feedback/tests/test_facts.py](tests/test_facts.py)
- [dagu/workflow-services/analytical-feedback/tests/test_identity_feedback.py](tests/test_identity_feedback.py)
- [dagu/workflow-services/analytical-feedback/tests/test_recognition.py](tests/test_recognition.py)
- [dagu/workflow-services/analytical-feedback/tests/test_saved_models.py](tests/test_saved_models.py)
- [dagu/workflow-services/analytical-feedback/tests/test_service.py](tests/test_service.py)
- [dagu/workflow-services/feedback-generation/README.md](../feedback-generation/README.md)
- [dagu/workflow-services/feedback-generation/src/main.py](../feedback-generation/src/main.py)
- [dagu/workflow-services/one-to-one-graph-matching/README.md](../one-to-one-graph-matching/README.md)
- [dagu/workflow-services/one-to-one-graph-matching/src/facts.py](../one-to-one-graph-matching/src/facts.py)
- [dagu/workflow-services/one-to-one-graph-matching/src/initial_recognition.py](../one-to-one-graph-matching/src/initial_recognition.py)
- [dagu/workflow-services/one-to-one-graph-matching/src/main.py](../one-to-one-graph-matching/src/main.py)
- [dagu/workflow-services/one-to-one-graph-matching/tests/test_main.py](../one-to-one-graph-matching/tests/test_main.py)
- [dagu/workflows/model-evaluation-graph-matching.yaml](../../workflows/model-evaluation-graph-matching.yaml)
- [docker-compose.yaml](../../../docker-compose.yaml)
- [web/src/components/modeling/editors/EvaluationEditor.vue](../../../web/src/components/modeling/editors/EvaluationEditor.vue)
- [web/src/components/modeling/sidebars/AnalyticalFeedbackPanel.vue](../../../web/src/components/modeling/sidebars/AnalyticalFeedbackPanel.vue)
- [web/src/components/modeling/sidebars/EvaluationSidebar.vue](../../../web/src/components/modeling/sidebars/EvaluationSidebar.vue)
- [web/src/model/DiagramLanguage.ts](../../../web/src/model/DiagramLanguage.ts)
- [web/src/utils/analysisFeedback.ts](../../../web/src/utils/analysisFeedback.ts)
- [web/src/utils/analysisFeedbackGraph.ts](../../../web/src/utils/analysisFeedbackGraph.ts)
- [web/src/utils/languageEvaluation.ts](../../../web/src/utils/languageEvaluation.ts)
