# Synonym Matching – Übergabestand

Ausgewählte Pipeline: **Jina DE/EN + OdeNet zuerst + WordNet-Fallback +
sprachübergreifende Synsetverknüpfung**, Jina-Threshold **0,85**.
Direkter Aufruf auf frischen Labelmengen; keine historischen Ergebnisdateien nötig.
Dieser Ordner ist die Methodenreferenz für die Übernahme, kein registrierter
Ersatz des bestehenden produktiven Workflow-Service.

## Lokal starten

Alle Befehle aus `dagu/workflow-services/synonym-matching-louis`.
Eine vorhandene venv weiterverwenden; sonst mit Python 3.12 anlegen:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=src python scripts/download_models.py
PYTHONPATH=src python scripts/download_lexicons.py
PYTHONPATH=src python src/main.py --input examples/input.json
```

Die Vorbereitung lädt nur Jina (inklusive fester Architekturrevision), OdeNet 1.4
und WordNet `omw-en:1.4`. Lingua-Sprachmodelle gehören zum Python-Paket.
Matching lädt nichts nach. `HF_HOME` wählt den HF-Cache; Lexika liegen standardmäßig
in `.cache/lexicons/wn`. In einer Anwendung eine Pipelineinstanz wiederverwenden:

```python
from synonym_matching import MatchingPipeline

pipeline = MatchingPipeline()  # Modell erst bei erster nichtleerer Anfrage laden
result = pipeline.match(
    [{"id": "r1", "label": "Gebäude"}],
    [{"id": "s1", "label": "Building"}],
)
```

## Ablauf und Annahmen

1. Eingaben/IDs prüfen, Originaltexte und Metadaten erhalten.
2. Unicode/Leerraum normalisieren, vereinbarte Abkürzungen lösen, Identifier trennen.
   Für Strings zusätzlich Casefolding, Umlaut-/Trennerangleichung; für Jina Großschreibung erhalten.
3. Damerau-Levenshtein und Jina-Cosinus für alle Paare berechnen.
4. Vorbereitetes Label in OdeNet suchen. Nur wenn unbekannt und Lingua sicher
   Englisch erkennt, WordNet wählen. Annahme: DE/EN; kein `language`-Feld nötig.
5. Bei unterschiedlichen Quellen OdeNet-Synsets über `wn.translate()` auf Englisch
   abbilden. Fehlender Eintrag/Link bleibt unbekannt, keine negative Evidenz.
6. Entscheiden: leer → nicht auswertbar; gemeinsames Synset → bestätigt;
   Gegenrelation → bei einer Lesart je Label abgelehnt, sonst offen;
   danach kanonisch gleich, Schreibähnlichkeit ≥0,85 oder Jina ≥0,85 → bestätigt;
   sonst offen. Zahlenkonflikt blockiert die Textstufen; ungleicher Wortanfang
   blockiert nur Stringevidenz. Synsetevidenz hat weiterhin Vorrang.

Path/Wu-Palmer werden mit Abdeckungsindikator berechnet, beeinflussen keine Entscheidung.
Ein gemeinsames Synset ist eine mögliche gemeinsame Lesart, keine Kontextdisambiguierung.
Keine willkürliche Kompositazerlegung, keine zusätzliche Embedding-Pflicht für Synsets.
Die frühere optionale Gleichheitspriorität bleibt als `exact_first=True` ein Experiment.

## Ein- und Ausgabe

CLI: `examples/input.json`, alternativ stdin oder `TEMPLATE_INPUT`.
`input.threshold` überschreibt **nur die Jina-Bestätigungsgrenze**, kein Ausgabefilter.
Alle Paare bleiben erhalten, einschließlich leerer Labels und unterschiedlicher Mengengrößen.
Gleiche Labels mit verschiedenen IDs sind erlaubt; doppelte IDs innerhalb einer Seite nicht.
Ohne IDs sind Stringlisten erlaubt; sie bekommen lokale IDs `r:0` bzw. `s:0`.

```json
{
  "synonymMatrix": [{
    "referenceElement": {"id": "r1", "label": "Gebäude"},
    "matches": [{
      "submissionElement": {"id": "s1", "label": "Building"},
      "scores": {"damerau_canonical": 0.0, "embedding_similarity": 0.0,
                 "pair_known": 1.0, "shared_synset": 1.0},
      "verdict": "confirmed", "reason": "shared_synset"
    }]
  }]
}
```

Scores oben sind gekürzte illustrative Werte. Tatsächlich werden alle Abdeckungs-,
Synsetanzahl-, Relations- und Taxonomiemerkmale ausgegeben. `pair_known` bezeichnet
gemeinsam auswertbare Evidenz; `reference_known`/`student_known` kennzeichnen die
einzelne Abdeckung. Path/Wu-Palmer 0 bei `taxonomy_available=0` ist unbekannt.
`reference_linked`/`student_linked` kennzeichnen ein verfügbares Profil in der
gemeinsamen Vergleichsquelle (direkt oder verknüpft), keine Übersetzungsqualität.

`verdict`: `confirmed`, `open`, `rejected`, `not_evaluable`. Kein künstlicher
`combinedScore`: Der Baum liefert Entscheidungen, keine kalibrierte Wahrscheinlichkeit.
Entscheidungen erfolgen ungerundet, JSON rundet Scores auf vier Nachkommastellen.
Ein gerundeter Score kann deshalb scheinbar eine Schwelle erreichen, obwohl das
Paar offen bleibt. `open` bedeutet weder falsches noch fehlendes Modellelement.
Verbindliche Standalone-Schemas: `schemas/`; **nicht** `semantic-candidates/v1`.

## Dateien

| Datei | Aufgabe |
|---|---|
| `src/main.py` | JSON-Einstieg und Schema-Prüfung |
| `src/synonym_matching/pipeline.py` | Gemeinsamer direkter Laufzeitkern |
| `preprocessing.py` | Ausgewählte Textformen/Abkürzungen |
| `methods.py` | Damerau und gepinnte Sentence-Embeddings |
| `lexicons.py` | OdeNet/WordNet, Lingua-Routing, Relationen/Links |
| `decision.py` | Eine Entscheidungslogik für Service und Forschung |
| `research/compare.py`, `experiments.json` | Ein Vergleichsbefehl, austauschbare Konfigurationen |
| `research/data/` | Vollständig annotierte, eingefrorene Eingabemengen |
| `tests/` | Sechs fachliche Testdateien, keine Modellausführung im Standardlauf |
| `experiments/` | Weiter ausführbarer und erweiterbarer bisheriger JSON-Baukasten mit eigenen Tests |

## Vergleich und Tests

```sh
PYTHONPATH=src python -m research.compare --output results/vergleich.json
python -m pytest -q
RUN_MODEL_TESTS=1 python -m pytest -m integration -q
```

Der Vergleich berechnet alle Rohmerkmale aus Labels, verwendet pro Konfiguration
denselben Kern wie der direkte Aufruf und prüft immer **0,80 / 0,85 / 0,90**.
`--only odenet_linked` beschränkt ihn auf den ausgewählten Kandidaten.
Dateinamen müssen neu sein; Ergebnisse werden nicht überschrieben.
Kein zusätzliches Markdown pro Lauf. JSON enthält Konfiguration, Seed, Revisionen,
Quellenhashes, vollständige Einzelergebnisse, P/R/F1, FP/FN, Roh-Embedding-Top-1
und Laufzeit (erste Modell-/Lexikonladung enthalten). Keine Top-1 aus binären Urteilen.
MiniLM/E5 bleiben über `embedding_model` konfigurierbar, benötigen separate Vorbereitung.

Auf geänderten Laborlabels, jeweils gegen alle Referenzkandidaten:

| Jina-Threshold | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| 0,80 | 163 | 1 | 29 | 0,9939 | 0,8490 | 0,9157 |
| **0,85** | **162** | **0** | **30** | **1,0000** | **0,8438** | **0,9153** |
| 0,90 | 153 | 0 | 39 | 1,0000 | 0,7969 | 0,8870 |

Kontrolle bei 0,85: 36 TP / 2 FP, F1 0,8889; gezielte Fälle: 5 TP / 0 FP.
Der direkte Lauf reproduziert diese Werte ohne vorgegebene Sprachinformationen.
Bekannte Entwicklungsdaten: reale Laboraufgabe mit konstruierten Varianten,
keine unabhängige Sammlung authentischer studentischer Abgaben. Von den fünf
Laborvarianten enthält eine auch englische Labels. Modell-/Thresholdwahl ist vorläufig.

## Bisherige Experimente weiterverwenden

Der vollständige bisherige Baukasten bleibt ausführbar und erweiterbar:

```sh
pip install -r experiments/requirements-research.txt
python scripts/run_experiments.py compare --output results/alle-experimente.json
python scripts/run_experiments.py tests -q
```

Konfiguration: `experiments/research/experiments.json`; Methoden:
`experiments/src/synonym_matching/methods.py`. Der neue ausgewählte Kern bleibt
davon unabhängig. Der Starter verwendet einen getrennten Python-Prozess und teilt
den bestehenden Modellcache/Ergebnisordner über lokale, ignorierte Verzeichnislinks.
Keine zweite venv oder Modellkopie nötig. Details: [experiments/README.md](experiments/README.md).

## Übergabe und Docker

**Übernahmeplan, Schnittstellenunterschiede und verbleibende Arbeit:** [HANDOVER.md](HANDOVER.md).
Das produktive System wurde nicht geändert. Pool und Graphkontext bleiben dortige Aufgaben.
Die alte Prototyp-CLI samt `capability.yaml` liegt unter `experiments/`; keine neue Workflowregistrierung.

Optionales Standalone-Image:

```sh
docker build -t synonym-matching-handover .
docker run --rm --network none -i synonym-matching-handover < examples/input.json
```

Image enthält nur Kern, Schemas, Vorbereitung und ausgewählte Ressourcen;
keine alten Experimente, kein spaCy, keine statischen Wortvektoren.
Docker-Build wurde bei der Übergabevorbereitung nicht ausgeführt: lokaler Daemon nicht erreichbar.
Native Python-/CLI- und Offline-Modelle werden separat geprüft.
