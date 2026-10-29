# Synonym Matching — lokaler Forschungsprototyp

Vorbereitung für [Issue #19](https://github.com/thm-mni-ii/modeling-copilot/issues/19).
Die Engine vergleicht **Referenzzeilen × studentische Spalten** und erhält IDs und
Originaltexte. Sie liefert Ähnlichkeiten und Kandidaten, keine fachlich bestätigte
Zuordnung, Bewertung oder erzwungene Eins-zu-eins-Zuordnung.

## Aktueller Prüfstand

Die Basistests und beide echten Modellpfade wurden lokal erfolgreich ausgeführt.
Nach dem Umbau werden zusätzlich Funktionskomposition, Pipeline-Reihenfolge und
das Hinzufügen einer eigenen Methode geprüft. Docker-Builds und eine vollständige
wissenschaftliche Benchmark-Auswertung sind noch offen. Die Requirements pinnen
direkte Abhängigkeiten; das Paketmanifest eines Experiments erfasst auch transitive
Abhängigkeiten für die Wiederholung.

Es gibt noch keine gemessenen Qualitäts- oder Laufzeitergebnisse. Die synthetischen
Annotationen sind technische Testdaten, keine unabhängig geprüfte Ground Truth.
Die Workflow-Anbindung, reale Modellexporte und Deployment übernimmt ein Kollege.

## Lokal starten (Python 3.12)

Alle folgenden Befehle aus diesem Verzeichnis ausführen:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python src/main.py --input examples/input.json
python -m pytest -m 'not integration'
```

Alternativ JSON über stdin oder die bestehende Umgebungsvariable `TEMPLATE_INPUT`.
`--input` hat Vorrang vor `TEMPLATE_INPUT`, diese hat Vorrang vor stdin. Erfolg:
Exit 0 und genau eine JSON-Zeile auf stdout. Fehler: Exit 1, Diagnose auf stderr,
kein erfolgreiches Teilergebnis. Modell-Downloads dürfen zusätzliche Diagnoseausgaben
auf stderr erzeugen.

Die Python-Schnittstelle ist unabhängig von Dagu, MongoDB und FastAPI:

```python
from synonym_matching import MatchingEngine  # PYTHONPATH=src

engine = MatchingEngine({
    "methods": ["levenshtein", "damerau_levenshtein", "jaro_winkler", "char_trigram"],
    "preprocessing": {"normalize": True, "lowercase": True},
    "combiner": {"kind": "mean"},
    "seed": 42,
})
result = engine.match(
    [{"id": "r1", "label": "Kunde", "language": "de"}],
    [{"id": "s1", "label": "Kund", "language": "de"}],
    threshold=0.5,
)
```

Der Python-Kern akzeptiert auch Stringlisten; deren IDs sind `reference:0` bzw.
`student:0` usw. Der JSON-Vertrag verlangt explizite IDs. Eine wiederverwendete
Engine hält Modelle und Caches im Speicher.

## Funktionen kombinieren und erweitern

- `preprocessing.py`: `normalize`, `lowercase`, `lemmatize`, `split_identifiers`.
- `methods.py`: eine Funktion pro Similarity-Verfahren, jeweils zwei Listen → Matrix.
- `combiners.py`: `mean`, `maximum`, `weighted_mean`.
- `engine.py`: orchestriert diese Funktionen und ergänzt IDs, Metadaten und Kandidaten.

Ein ausführbares Beispiel ohne Engine: `PYTHONPATH=src python examples/functions.py`.
Eigene Preprocessing-Funktionen haben die Signatur `(text, language=None)` und
können direkt an `apply_pipeline(text, [normalize, eigene_funktion])` übergeben
werden. Die Reihenfolge ist frei wählbar; eine leere Liste bedeutet keine Schritte.

Für JSON-Konfigurationen werden dieselben Schritte über Namen ausgewählt:

```json
{"preprocessing": ["normalize", "lowercase"],
 "methods": ["levenshtein", "jaro_winkler"],
 "combiner": {"kind": "mean"}}
```

Die bisherigen Boolean-Konfigurationen funktionieren weiterhin in der bisherigen
Reihenfolge. Python-Funktionen direkt in `apply_pipeline` verwenden; persistierte
Experimentkonfigurationen enthalten Namen, keine Python-Funktionsobjekte.

Eine eigene Methode benötigt keine Änderung an der Engine:

```python
from synonym_matching.methods import METHODS

def verfahren_xy(left, right):
    # Berechne eine NumPy-Matrix mit Shape (len(left), len(right)).
    ...

METHODS["verfahren_xy"] = verfahren_xy
# Danach in config.methods den Namen "verfahren_xy" wählen.
```

Eigene Textschritte analog in `preprocessing.STEPS` registrieren. Registrierungen
müssen im aufrufenden Prozess vor dem Aufbau der Engine stattfinden; für CLI-Läufe
werden neue Funktionen im jeweiligen Modul definiert und dort eingetragen.

Nur Modellzustand und Caches bleiben in kleinen Hilfsklassen. Bei Embeddings
stellt die Engine das Backend bereit und bereitet Übersetzungen batchweise vor.
Die Funktionen `multilingual_embedding` und `translated_embedding` erhalten dieses
Backend explizit. So werden Modelle und identische Labels nicht je Paar neu geladen
oder berechnet. Direkte Kombinatorfunktionen aggregieren die übergebenen Werte;
der Engine-Adapter `combine` übernimmt vorher die dokumentierte Cosinus-Begrenzung.

## Eingabe und Ausgabe

Siehe [vollständiges Beispiel](examples/input.json),
[Input-Schema](schemas/input.schema.json) und [Output-Schema](schemas/output.schema.json).
Der Service validiert das Input-Schema und danach die fachlichen Konfigurationsbedingungen.

```json
{
  "step": "synonym_matching",
  "input": {
    "referenceModel": {"elements": [{"id": "r1", "label": "Kunde", "language": "de"}]},
    "studentModel": {"elements": [{"id": "s1", "label": "Kund", "language": "de"}]},
    "threshold": 0.5,
    "config": {"methods": ["levenshtein"]}
  }
}
```

`result` enthält:

- `referenceElements`, `studentElements`, `shape`: Achsen in Eingabereihenfolge.
- `scores`: vollständige Einzelmatrizen, auch unterhalb des Thresholds.
- `combinedScores`: vollständige kombinierte Matrix.
- `synonymMatrix`: pro Referenz Kandidaten mit `submissionElement`, `scores`,
  `combinedScore`, `rank`, `mutualBest`; dazu `top1Top2Margin` pro Referenz.
- `processedLabels`: tatsächliche Eingabetexte pro Methode, einschließlich der
  übersetzten/weiterverarbeiteten Texte beim Übersetzungspfad.
- `config`, `threshold`, `metadata`: Parameter, Modellrevisionen, Laufzeiten,
  Cache-Zähler und Score-Policy.

Threshold bedeutet `combinedScore >= threshold`, `null` bedeutet ungefiltert.
Es gilt keine globale Eins-zu-eins-Beschränkung. Der Rang wird vor dem Filter
bestimmt. Gleichstände behalten die ursprüngliche Spaltenreihenfolge;
`mutualBest` kann bei Gleichstand für mehrere Paare gelten. Eine fehlende zweite
Option hat Margin `null`, nicht eine erfundene hohe Sicherheit.

Leere Listen sind gültig, `shape` bleibt maßgeblich (JSON `[]` kann 0×N nicht allein
abbilden). Leere/Whitespace-Labels erhalten Score 0 und sind auch bei Threshold 0
keine Kandidaten. Wiederholte Labels mit verschiedenen IDs bleiben getrennt;
doppelte IDs innerhalb einer Seite sind Fehler. String- und Integer-IDs bleiben
typgetreu erhalten und sind unterschiedliche IDs. IDs verschiedener Seiten dürfen
gleich sein. Es findet keine automatische XML-/HTML-Interpretation statt.

## Verfahren und Scores

| Name | Verfahren |
| --- | --- |
| `levenshtein` | RapidFuzz normalisierte Levenshtein-Similarity |
| `damerau_levenshtein` | Echtes Damerau-Levenshtein, nicht OSA |
| `jaro_winkler` | RapidFuzz Jaro-Winkler-Similarity |
| `char_bigram`, `char_trigram` | Jaccard auf Zeichen-n-Gramm-Mengen; kurze nichtleere Texte ergeben ein einzelnes Gramm |
| `multilingual` | Sentence-Embedding direkt, Cosinus |
| `translated_embedding` | Deutsch → Englisch, dann englisches Sentence-Embedding, Cosinus |

String-Scores liegen in [0,1], rohe Cosinus-Scores in [-1,1]. Kombinatoren verwenden
`clip(score, 0, 1)`; Rohscores werden nicht verändert. Scores sind keine
kalibrierten Wahrscheinlichkeiten, auch die Lernmodelle werden nicht als solche
beworben. Mean, Max und Weighted Mean garantieren keine Verbesserung.

`combiner.kind`: `mean`, `max`, `weighted_mean`. Optional wählt
`combiner.methods` eine geordnete Teilmenge der berechneten Methoden. Gewichte
müssen genau diese Namen abdecken, endlich und nichtnegativ sein und eine positive
Summe haben; die Summe wird normalisiert.

```json
{"kind": "weighted_mean", "methods": ["damerau_levenshtein", "multilingual"],
 "weights": {"damerau_levenshtein": 0.25, "multilingual": 0.75}}
```

## Preprocessing und Ablationen

`preprocessing` steuert Strings, `embedding_preprocessing` separat Embeddings.
Standard ist nur NFC-Unicode-Normalisierung und Zusammenfassen von Whitespace.
Optionen: `normalize`, `lowercase`, `lemmatize`, `split_identifiers` (je Boolean).
Keine standardmäßige Entfernung von Negation, Satzzeichen oder Umlauten.

Reihenfolge: Normalisierung → optional camelCase/underscore trennen → optional
Lemmatisierung → optional Lowercasing. Lemmatisierung benötigt explizit `de`/`en`
und die entsprechenden spaCy-Pakete. Sie arbeitet vor Lowercasing, um z.B. deutsche
Substantivhinweise zu erhalten. Fehlerhafte Sprachen werden nicht still geraten.

Beim übersetzten Embedding folgt danach Übersetzung → `target_preprocessing`
auf Englisch → Encoder. Der multilinguale Encoder erhält keine Übersetzung.
Das englische MiniLM verwendet intern einen uncased Tokenizer; eine explizite
Lowercasing-Ablation muss dort nicht dieselbe Wirkung haben wie bei Strings.

## Optionale Modelle

```sh
python -m pip install -r requirements.txt
python -m spacy download de_core_news_sm
python -m spacy download en_core_web_sm
```

Die tatsächlich installierten spaCy-Modellversionen werden durch den Runner im
Paketmanifest gespeichert. Für eine Wiederholung genau diese Versionen verwenden.

| Pfad | Standardmodell | Auswahlgrund / Einschränkung |
| --- | --- | --- |
| Multilingual | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | 384 Dimensionen, ca. 0,1B Parameter, 50 Sprachen; kein Übersetzungsschritt |
| Englisch | `sentence-transformers/all-MiniLM-L6-v2` | 384 Dimensionen, sechs Schichten; kompakter Encoder |
| DE → EN | `Helsinki-NLP/opus-mt-de-en` | Sprachpaarspezifische lokale Übersetzung; ca. 298 MB PyTorch-Gewichte, zusätzlicher Rechenaufwand |

Die Modellkarten nennen Apache-2.0. Qualitäts- und Laufzeitvorteile für eure Labels
sind erst zu messen. Quellen:
[Multilingual](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2),
[Englisch](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2),
[Übersetzung](https://huggingface.co/Helsinki-NLP/opus-mt-de-en).

Konfiguration pro Embedding-Methode unter `embedding`:
`model`, `revision`, `batch_size`; beim Übersetzungspfad zusätzlich
`translation_model`, `translation_revision`, `target_preprocessing`.
Standardrevision ist `main`, die geladene Commit-ID wird protokolliert. Für
wiederholbare Forschungsruns diese IDs explizit setzen. CPU ist bewusst fest
vorgegeben. Zu lange Labels werden abgelehnt statt unbemerkt abgeschnitten.

DE-Texte werden einmal je eindeutigem Text übersetzt, EN-Texte durchgereicht.
Andere/fehlende Sprachen sind für diesen Pfad ein Fehler. Modelle laden erst bei
Bedarf. Die Engine hält berechnete Übersetzungen und Embeddings im Arbeitsspeicher.
Identische verarbeitete Texte teilen Features, IDs bleiben getrennt. Eine neue
Engine beginnt mit leerem Featurecache. Der separate Downloadcache der
Hugging-Face-Bibliothek bleibt unverändert; Gewichte werden nicht jedes Mal erneut
heruntergeladen.

```sh
RUN_MODEL_TESTS=1 python -m pytest -m integration
```

Diese Tests prüfen tatsächliche Ausführung und Wiederverwendung, keine behauptete
semantische Trefferquote. Sie laden Modelle und benötigen Netz oder gefüllten
Hugging-Face-Cache. Für Modellgewichte optional `HF_HOME` auf einen lokalen,
nicht versionierten Cache setzen.

## Experimente

```sh
PYTHONPATH=src python -m synonym_matching.evaluation \
  --data experiments/data/synthetic.json \
  --suite experiments/configs/baselines.json \
  --output results/baseline-001

PYTHONPATH=src python -m synonym_matching.evaluation \
  --data experiments/data/synthetic.json \
  --suite experiments/configs/full.json \
  --output results/full-001
```

Ausgabeordner müssen neu sein. Fehler einzelner Varianten werden gespeichert;
der gesamte Befehl liefert dann Exit 1. Ein fehlendes Modell wird nicht durch
String-Scores ersetzt. Details zu Daten, Leakage und Metriken:
[Experimentprotokoll](experiments/README.md).

Logistic Regression und Random Forest werden direkt im Experiment-Runner trainiert
und ausgewertet. Gespeichert werden Parameter, Scores und Metriken, kein eigenes
Modellformat. Zur Wiederholung wird mit derselben Konfiguration und demselben
Datensplit erneut trainiert.

## Hinweise für die Anbindung

Die Anbindung übernimmt der Kollege. Einstieg:
`MatchingEngine(config).match(reference, student, threshold=None)`; alternativ der
CLI-Adapter `src/main.py`. Die Listen unter `referenceModel.elements` und
`studentModel.elements` kommen vom Aufrufer/Parser. Der Service liest kein XML und
löst keine Datenbankreferenzen auf.

Gegenüber dem ursprünglichen Skeleton:

- `input.source`, ein alleiniger `step` und `demoDelaySeconds` sind keine gültigen
  Matching-Eingaben mehr.
- `result.matches` mit Dummy-Paaren wird durch vollständige Matrizen und
  `result.synonymMatrix` ersetzt.
- Der äußere Envelope `status`, `capability`, `step`, `summary`, `result` bleibt.
- stdout enthält eine JSON-Zeile; Logs/Fehler gehen auf stderr.

Dockerfile und Image-Version bleiben auf dem ursprünglichen Skeleton-Stand.
**Der bisherige Container ist damit noch nicht für den neuen Python-Code vorbereitet:**
Er installiert keine Abhängigkeiten und kopiert keine Schemas. Der Kollege muss
Installation, Schema-Dateien, Modellbereitstellung und tatsächliche Workflow-Eingaben
bei der Anbindung gemeinsam ergänzen. Bis dahin lokal mit der `.venv` ausführen.
Die Capability-Description beschreibt bereits die neue Funktionalität.

Für den späteren Betrieb außerdem RAM-/CPU-Bedarf und Loggrößen mit realistischen
Modellen messen. Die bisherigen Dagu-Defaults sind kein geprüfter ML-Ressourcenplan.
Mehrere Kandidaten und gleiche Labels mit unterschiedlichen IDs sind absichtlich
zulässig; die strukturelle Graphzuordnung liegt außerhalb dieser Engine.
