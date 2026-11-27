# Übergabe: ausgewählte Synonym-Matching-Pipeline

## Stand

**Getesteter Matching-Kern als Methodenreferenz; noch nicht produktiv angebunden.**
Ein direkter Aufruf verarbeitet frische Labelmengen ohne historische Ergebnisse oder
Sprachangaben. Die Anbindung erfolgt in der vorhandenen produktiven Architektur,
ohne zusätzliches Integrationspaket. Produktivordner wurden nicht verändert.

```python
# In diesem Ordner mit PYTHONPATH=src:
from synonym_matching import MatchingPipeline

pipeline = MatchingPipeline()  # Instanz für wiederholte Anfragen behalten
result = pipeline.match(reference_elements, student_elements)
```

Einrichtung und CLI: `README.md`, `examples/input.json`.
Kern: `src/synonym_matching/{pipeline,preprocessing,methods,lexicons,decision}.py`.

## Was die Pipeline macht und warum

| Reihenfolge | Verfahren / Regel | Zweck |
|---|---|---|
| 1 | Unicode/Leerraum normalisieren, bekannte Kürzel lösen, Identifier trennen | Schreibvarianten vorbereiten; Originaltexte und IDs erhalten |
| 2 | Damerau-Levenshtein auf kanonischer Textform | Tippfehler und Zeichenvertauschungen erkennen |
| 3 | **Jina DE/EN**, normierte Embeddings, Cosinus | Deutsch/Englisch semantisch vergleichen; neues Modell statt bisherigem MiniLM |
| 4 | OdeNet zuerst; fehlt ein Eintrag und Lingua erkennt Englisch, WordNet | Deutsche Begriffe bevorzugen und englische Eingaben berücksichtigen |
| 5 | Unterschiedliche Lexikonquellen über `wn.translate()` verbinden | Gemeinsame Bedeutungen etwa für Gebäude/Building finden; keine maschinelle Textübersetzung |
| 6 | Baum: gemeinsames Synset → Gegenrelation → Stringgleichheit/Schreibähnlichkeit → Embedding → offen | Explizite Bedeutungsrelationen zusätzlich zur allgemeinen Ähnlichkeit verwenden |

Gewählt: **String ≥0,85 und Jina ≥0,85**. Leere Labels sind nicht auswertbar.
Gegenrelationen führen bei einer Lesart je Label zur Ablehnung, sonst zu offen.
Gemeinsame Synsets haben auch bei mehreren Lesarten Vorrang. Zahlenkonflikte
blockieren die Textstufen, unterschiedliche Wortanfänge nur Stringevidenz.
Path/Wu-Palmer sind diagnostisch, ohne aktive Filterwirkung.

Abdeckung bleibt separat sichtbar: kein Eintrag/Link ist kein Gegenbeweis.
Hohe Ähnlichkeit oder ein gemeinsames Synset garantieren keine fachlich passende
Lesart. `open` bedeutet nicht automatisch falsch oder fehlend. Kein kalibrierter
Combined Score; Rohmerkmale nicht einfach zu einer Wahrscheinlichkeit mitteln.

## Neue Ressourcen für den produktiven Build

| Ressource | Festlegung |
|---|---|
| **Neues Embedding** | `jinaai/jina-embeddings-v2-base-de`, Revision `3f9eede875721714945b6a99a3198299243cf2be` |
| Separate Jina-Architektur | `jinaai/jina-bert-implementation`, Revision `f3ec4cf7de7e561007f27c9efc7148b0bd713f81` |
| Deutsches Bedeutungsnetz | OdeNet `odenet:1.4` |
| Englisches Bedeutungsnetz | WordNet `omw-en:1.4`, auch für Synsetverknüpfungen erforderlich |
| Neue Pakete | `wn==0.14.0`, `lingua-language-detector==2.2.0` |
| Spracherkennung | Lingua nur DE/EN, Mindestabstand 0,2; Modelle im Python-Paket |

Jina ersetzt im ausgewählten Kandidaten
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`; MiniLM als Baseline
behalten. Jina benötigt seine eigene gepinnte Architektur (`trust_remote_code`).
Vorbereitungsvorlage: `scripts/download_models.py`, `scripts/download_lexicons.py`.
Lizenzen der Modelle/Pakete/Lexikondaten berücksichtigen. Ressourcen beim Build
bereitstellen; Matching bleibt offline. Keine Übersetzungs-, spaCy- oder statischen
Wortvektormodelle für den ausgewählten Kern nötig.

## Konkrete produktive Einfügestellen

| Datei / Bereich | Bei der Übernahme beachten |
|---|---|
| `synonym-matching/.../methods/registry.py` | Jina und benötigte numerische Lexikonmerkmale registrieren; alte Methoden behalten |
| `synonym-matching/.../service.py` | Rohmerkmale für die bestehenden zulässigen Kandidaten berechnen; vorhandene Zusatzquellen/Notationssegmente erhalten |
| `one-to-one-graph-matching/src/text_similarity.py` | `decision.decide(...)` als fachliche Referenz nutzen; Urteil in den bestehenden Text-Evidenzvertrag übertragen |
| `workflow-data/src/main.py`, `apply_text_evidence()` | **Fixiert bisher alte Methodennamen und Textstufen.** Neue Policy vor Snapshot-Hashbildung ergänzen, sonst wird Jina nicht aktiviert |
| `dagu/infra/workflow-services.yaml` | Images aktualisieren; bestehendes Warmup lädt MiniLM – die neue Jina-Initialisierung entsprechend vorbereiten |
| `synonym-matching/.../signals.py`, `_rank()` | Zählwerte, Abdeckung und Taxonomiewerte nicht als hohe Matching-Konfidenz für Pool-Vorschläge behandeln |

Die Standalone-main.py und Schemas dieses Ordners **nicht** über den produktiven
V1-Workflowvertrag kopieren. Methoden übernehmen oder den Kern unter eigenem
internen Paketnamen ablegen; kein Runtime-Import aus dem Louis-Ordner nötig.
`MatchingPipeline.features(...)` liefert ungerundete Einzelmerkmale;
`decision.decide(...)` entscheidet. Die Standalone-Ausgabe mit `verdict`/`reason`
ist noch nicht `semantic-candidates/v1`.

**Erhalten:** manuell accepted/rejected aus dem Synonym-Pool vor automatischer
Evidenz behandeln. Zusatzquellen und Segmente jeweils separat bewerten, nicht
Scores verschiedener Quellen vermischen. Typfilter, Kontext und globale Zuordnung
bleiben im Graphmatcher; Textbestätigung allein ist keine 1:1-Zuordnung.
Neue Konfigurationen nur in neue Snapshots übernehmen, alte Artefakte nicht ändern.
API-/Frontend-Methodennamen und `api/.../services/text_forms.py` bei der Anzeige prüfen.

## Ergebnisse und Abnahme

```sh
python -m pytest -q
RUN_MODEL_TESTS=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python -m pytest -m integration -q
PYTHONPATH=src python -m research.compare --output results/neuer-vergleich.json
```

Vergleiche weiterhin bei **0,80 / 0,85 / 0,90**, mit Precision/Recall/F1, FP/FN,
Roh-Embedding-Top-1 und Laufzeit. Daten/Herkunft: `research/data/`;
Referenzwerte: `research/baseline-results.json`.
Bei 0,85: Labor **162 TP / 0 FP / 30 FN**, Recall 0,8438, F1 0,9153;
Kontrolle 36 TP / 2 FP. Bekannte Entwicklungsdaten, keine allgemeine Garantie.

Direkter Kern, CLI und lokale Modelle/Lexika sind geprüft; der produktive
Gesamtlauf mit Pool/Segmenten/Graphkontext steht noch aus. Docker-Build wurde
wegen nicht erreichbarem lokalem Daemon nicht geprüft. Ressourcenbedarf unter
dem bestehenden 2-GiB-Containerlimit ist noch nicht lastgetestet.

Bisherige Experimente bleiben vollständig ausführbar und erweiterbar:
`python scripts/run_experiments.py compare --output results/weitere-versuche.json`.
Details und eigene Tests: `experiments/README.md`.
