# Übergabe – Synonym-Matching

## Was fertig ist

Ein kleiner direkter Python-Kern verarbeitet neue Labelmengen ohne historische
Ergebnisdateien oder vorgegebene Sprache. Serviceaufruf und Forschung verwenden
dieselbe Implementierung und dieselben ungerundeten Entscheidungen.

Ausgewählt: **Jina DE/EN + OdeNet zuerst + englisches WordNet als Fallback +
Synsetverknüpfung über wn**, Jina ≥0,85, Damerau ≥0,85. Path/Wu-Palmer nur diagnostisch.
Kern und Aufruf: `src/synonym_matching/`, `src/main.py`.
Beispiel: `examples/input.json`. Einrichtungsbefehle stehen in `README.md`.

Echte lokale Ressourcen und CLI wurden offline geprüft. Bei frischer Berechnung:
Labor 162 TP / 0 FP / 30 FN, Kontrolle 36 TP / 2 FP, gezielte Probe 5 TP / 0 FP.
Vergleich bei 0,80/0,85/0,90 ist reproduzierbar; kompakte Referenzwerte und
Quellenhashes stehen in `research/baseline-results.json`.
Die Testdaten enthalten ihre Herkunft und vollständige Paarannotationen.
Das sind bekannte Entwicklungsdaten, keine unabhängige Qualitätsgarantie.

## Wichtig: noch keine produktive Integration

Das bestehende Produktivsystem wurde **nicht geändert**. Dieser Ordner ist gemäß
produktiver README eine Methodenreferenz. Kein Laufzeitimport aus dem Louis-Ordner,
kein Mount dieses Ordners, keine zweite Workflowregistrierung nötig.
Alte Varianten sind unter `experiments/` weiterhin ausführbar und erweiterbar.
Starter: `python scripts/run_experiments.py compare --output results/versuch.json`;
eigene Tests: `python scripts/run_experiments.py tests -q`.
Sie werden vom ausgewählten Kern nicht importiert oder ins aktuelle Image kopiert.
Die alte `capability.yaml` liegt beim bisherigen Prototyp unter `experiments/`.

| Dieser Standalone-Kern | Bestehender produktiver Ablauf |
|---|---|
| Zwei Listen mit lokalen IDs/Labels | V1-Inventare mit Quellen-/Snapshotbindung |
| `synonymMatrix` mit Elementobjekten, numerischen Merkmalen, `verdict`/`reason` | `workflow-result/v1` mit `semantic-candidates/v1`, Methoden, Hashes, `scoreStatus` usw. |
| Vollständige Labelpaare, keine 1:1-Auswahl | Zulässige Kandidaten, Elementtypen, Segmente und nachfolgendes Graphmatching |
| Kein Pool, keine Graphbewertung | Glossareinträge, Kontext, Struktur und globale Zuordnung |

**Nicht unsere `main.py`, Schemas, gesamte Engine oder Dockerfile über die
produktiven Dateien kopieren.** Dortige Schnittstellen und Provenienz erhalten.
Der neue Standalone-Vertrag ersetzt bewusst die alte Forschungs-Combined-Score-CLI;
der vollständige alte Vertrag ist über `python scripts/run_experiments.py cli`
weiter aufrufbar. Er ist ebenfalls kein Produktivvertrag.

## Vorschlag für die Übernahme, in dieser Reihenfolge

1. **Kern übernehmen, Namespace trennen.** Die fünf Module plus `__init__.py`
   unter `src/synonym_matching/` lassen sich als eigenes internes Paket
   `selected_synonym_pipeline` in den produktiven Service kopieren. Sie verwenden
   relative Imports und benötigen keine Forschungsmodule. Alternativ einzelne
   Verfahren in die vorhandene Architektur übertragen; bestehende produktive
   `preprocessing.py` und `service.py` nicht blind überschreiben.
2. **Ressourcen vorbereiten.** Jina-Gewichte und separate Architekturrevision aus
   `methods.py` übernehmen; OdeNet `odenet:1.4` und WordNet `omw-en:1.4` im
   Build bereitstellen. `wn` und Lingua als neue Abhängigkeiten ergänzen.
   Skripte im Louis-Ordner zeigen die minimale Vorbereitung; ihre Paketimporte
   bei einer Umbenennung anpassen. Keine alten Übersetzungsmodelle, Wortvektoren
   oder spaCy-Modelle nötig. Lizenztexte von Jina/Lingua und beiden Lexika mitnehmen.
3. **Numerische Evidenz integrieren.** Anknüpfung:
   `synonym-matching/src/synonym_matching/methods/registry.py` und `service.py`.
   `MatchingPipeline.features(reference, student)` liefert vollständige Rohmerkmale
   und Quellenwahl. Vorhandene Kandidaten-/Typfilter, IDs, Hashes, `scoreStatus`,
   `matchingSources` und `segmentSources` erhalten. Jina ist eine zusätzliche
   Methode; bestehendes MiniLM bleibt als Vergleich verfügbar.
4. **Baum an der Entscheidungsstelle verwenden.** Im produktiven Ablauf liegt
   die Textinterpretation im Graphmatcher unter `src/text_similarity.py`, nicht
   allein im Score-Service. `decision.decide(...)` ist die fachliche Referenz.
   Übertragung von `verdict`/`reason` in den dortigen Evidenzvertrag ausdrücklich
   implementieren und testen. Zusätzliche Felder können Schemaänderungen benötigen:
   nicht ungeprüft in `semantic-candidates/v1` schreiben. Ein `confirmed`-Labelpaar
   ist ein Kandidat, noch keine verbindliche globale 1:1-Zuordnung.
5. **Poolvorrang bewahren.** Administratorbestätigungen/-ablehnungen aus dem
   vorhandenen Glossar weiter vor automatischer Evidenz behandeln. Kein Kopieren
   von Testannotationen in den Pool. Poolversion im Snapshot erhalten. Starke
   menschliche Entscheidung nicht nachträglich durch den Forschungsbaum aufheben.
6. **Gesamtpipeline testen.** Erst ausgewählte Methode gegen bisherigen Stand,
   dann mit Pool/Segmenten/Graphkontext; jeweils alle drei Jina-Thresholds. Bestehende
   produktive Tests und Workflow-/Schema-/Hash-Prüfungen ergänzen. Ergebnisse der
   Standalone-Labelbewertung sind keine End-to-End-Messung der Graphbewertung.

## Verwendbare Funktionen

```python
from selected_synonym_pipeline import MatchingPipeline

pipeline = MatchingPipeline()  # langlebige Instanz, Caches wiederverwenden
raw = pipeline.features(reference_elements, student_elements)
matrix = pipeline.from_features(raw)  # 0,85; Entscheidungen vor Rundung
# Ohne Neuberechnung nur die Jina-Grenze ändern:
comparison = pipeline.from_features(raw, meaning_threshold=0.80, decimals=None)
```

Das Beispiel setzt die Paketübernahme/Umbenennung aus Schritt 1 voraus.
Im Louis-Ordner heißt der Import weiterhin `synonym_matching`.
Lexika liegen standardmäßig relativ zum Service in `.cache/lexicons/wn`;
`lexicon_path=` erlaubt einen anderen lokalen wn-Datenpfad. `HF_HOME` steuert HF.
Eine Instanz je Prozess verwenden; parallele Requests/abweichende wn-Datenpfade
sind hier nicht lastgetestet. Kaltstart lädt Ressourcen, warme Anfragen nutzen Caches.

## Bekannte Grenzen und bewusste Entscheidungen

- Deutsch/Englisch angenommen. OdeNet-Treffer heißt nicht automatisch deutsche
  oder fachlich passende Bedeutung; Polysemie bleibt ungelöst.
- Lingua nur wenn OdeNet nichts findet; Mindestabstand 0,2 ist eine unvalidierte
  Heuristik. Unsicher bleibt ohne sichere Lexikonquelle. Kein Netzwerk zur Laufzeit.
- Gemeinsames Synset hat Vorrang vor lesartenübergreifenden Gegenrelationen und
  Textguards, entsprechend dem getesteten Stand. Keine zusätzliche Embedding-Pflicht.
- Zahlen-/Wortanfangs-Guards stammen aus dem produktiven Textpfad; keine neuen
  Spezialwortlisten außer vereinbarten Abkürzungen. Abkürzungsexpansion braucht
  jetzt keine Testdaten-Sprachangaben; Gesamtzahlen bleiben auf den Fällen gleich.
- Es gibt **keinen kalibrierten Combined Score**. Cosinus, Schreibähnlichkeit,
  Abdeckung und Synsetanzahlen nicht unkritisch mitteln. `open` ist keine Ablehnung.
- Path-/Wu-Palmer-Werte sind optimistische Maxima über mögliche Lesarten; die
  Maxima können von unterschiedlichen Synsetpaaren stammen. Fehlende Verbindung
  über `taxonomy_available` sichtbar halten; hohe Nähe bestätigt keine Synonymie.
- Die eingefrorenen Fälle enthalten bewusst Mehrdeutigkeit, konkurrierende
  Kandidaten, leere Labels und doppelte Texte. Annotationen sind Entwicklungsgold.
- Dockerfile vorbereitet, **nicht gebaut/getestet**, weil der lokale Docker-Daemon
  nicht erreichbar war. Vor produktiver Übernahme Build und Offline-Containerlauf prüfen.

## Abnahme bei der Übernahme

- Frische Inventare ohne `language`-Felder, deutsche und englische Labels laufen.
- `Gebäude ↔ Building` und `Anzahl ↔ Quantity` nutzen Synsetlinks, unbekannte
  Fachbegriffe bleiben von fehlender Gegenrelation unterscheidbar.
- Poolvorrang, Graphkontext, konkurrierende Kandidaten und nicht auswertbare
  Elemente werden weiterhin gemäß Produktivvertrag behandelt.
- Keine neuen Rundungsentscheidungen, keine stillen Modelldownloads, korrekte
  Ressourcen-/Konfigurationshashes, Schema validiert.
- CLI/Container offline, produktive Regressionstests und vollständige Laborfälle geprüft.
