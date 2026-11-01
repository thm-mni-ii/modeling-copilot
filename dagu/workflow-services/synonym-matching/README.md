# Synonym Matching

Zwei Labelmengen hinein, eine Synonymmatrix mit Original-IDs, Einzelscores und
Combined Score heraus. Der Service verarbeitet extrahierte Labels, kein Graph-XML.

## Zwei Ausführungspfade

- **Service:** `src/main.py` → `synonym_matching.service.match()` → Engine.
- **Forschung:** `research/compare.py` enthält die Konfigurationsliste und führt sie aus. Beide verwenden denselben Matching-Kern.

Der Service importiert keine Forschungsmodule. Docker enthält nur den Service,
Schemas und Vorbereitungsskripte. Forschungsergebnisse verändern den Standard nicht.

## Lokal starten

Alle folgenden Befehle im Ordner `dagu/workflow-services/synonym-matching`:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/main.py --input examples/input.json
```

Eine bereits vorhandene `.venv` nur aktivieren, nicht neu anlegen.
Die CLI liest alternativ JSON aus `TEMPLATE_INPUT` oder stdin und liefert eine
JSON-Zeile. Fehler erscheinen auf stderr mit Exitcode 1.

```python
from synonym_matching import match

result = match(["Kunde"], ["Kund"], config={"methods": ["levenshtein"]})
```

Für diesen Python-Aufruf `PYTHONPATH=src` setzen. Ohne Konfiguration gelten
Levenshtein, Damerau-Levenshtein, Jaro-Winkler, Zeichen-Bigramme und -Trigramme,
Unicode-/Leerraumnormalisierung und der einfache Mittelwert. Embeddings und
Lexika werden ausdrücklich über `config.methods` gewählt.

## Schnittstelle

```json
{
  "step": "synonym_matching",
  "input": {
    "referenceModel": {"elements": [{"id": "r1", "label": "Kunde", "language": "de"}]},
    "studentModel": {"elements": [{"id": "s1", "label": "Kund", "language": "de"}]},
    "config": {"methods": ["levenshtein"], "combiner": {"kind": "mean"}},
    "threshold": 0.5
  }
}
```

```json
{"synonymMatrix": [{"referenceElement": {"id": "r1", "label": "Kunde", "language": "de"}, "matches": [{"submissionElement": {"id": "s1", "label": "Kund", "language": "de"}, "scores": {"levenshtein": 0.8}, "combinedScore": 0.8}]}]}
```

Ohne Threshold bleiben alle nichtleeren Kandidaten enthalten. Treffer sind
absteigend sortiert; Gleichstände behalten die Eingabereihenfolge. Keine
1:1-Zuordnung im Service. Leere Mengen sind erlaubt, leere Labels keine Kandidaten.
Doppelte Labels mit unterschiedlichen IDs bleiben erhalten; doppelte IDs innerhalb
einer Seite sind ungültig. Erst die Ausgabe rundet Scores auf vier Stellen.

## Wo ändere ich was?

```text
src/main.py                      JSON einlesen und ausgeben
src/synonym_matching/
  service.py                     Matching-Ablauf und öffentlicher match()-Aufruf
  methods.py                     einzelne Similarity-Verfahren und Modellladen
  preprocessing.py               Textvorbereitung
  combinations.py                alle Kombinationen und Gewichtungen
  config.py                      Eingaben der Matching-Konfiguration prüfen
  translation.py, lexicons.py     Übersetzungs- und Lexikonzugriff
  cache.py                       Ergebnisse pro Label wiederverwenden
research/
  compare.py                     Konfigurationen festlegen und vergleichen
  evaluation.py                  Zuordnung und Metriken
  rank_results.py                Top 3 berechnen und lesbar ausgeben
  build_model_cases.py            Testdaten erzeugen
  model-cases.json                Testdaten mit erwarteten Zuordnungen
```

`MatchingEngine` bleibt als wiederverwendbares Objekt erhalten, damit Modelle und
berechnete Embeddings nicht für jedes Paar neu geladen werden. Es gibt keine
weiteren Runner-Klassen oder ein Plugin-Framework. Der Serviceausgang enthält nur
die Synonymmatrix, der Forschungslauf speichert seine vollständigen Ergebnisse.

## Verfahren und Modelle

- `methods.py`: String-/Tokenvergleiche, Exact Match, Wortreihenfolge,
  übersetzte Strings, Embeddings und Lexikonadapter.
- `preprocessing.py`: `normalize`, `lowercase`, `split_identifiers`, `lemmatize`,
  `stem`, `remove_stopwords`, `split_compounds`. Geordnete Liste, `[]` für Rohtexte.
- `combinations.py`: Mean, Max, Weighted Mean sowie feste
  Kombinationen und Regeln. `config.combiner` wählt die Kombination.
- `service.py`: `compute_scores()` liefert ungerundete NumPy-Matrizen;
  `match()` ergänzt Kombination und Kandidatenlisten. Keine globalen Seed-Änderungen.
- `cache.py`, `translation.py`, `lexicons.py`: Wiederverwendung pro Label und Engine.

Die zwei Embedding-Pfade verwenden standardmäßig
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` beziehungsweise
`sentence-transformers/all-MiniLM-L6-v2` nach `Helsinki-NLP/opus-mt-de-en`.
Das sind kompakte CPU-Ausgangsmodelle, keine nachgewiesenen Sieger für reale Abgaben.
Modellnamen und Revisionen sind über `config.embedding` austauschbar.

Lokale Ressourcen einmal vorbereiten:

```bash
PYTHONPATH=src python scripts/download_models.py
python scripts/download_lexicons.py
python -m spacy download de_core_news_sm
python -m spacy download en_core_web_sm
```

Downloads sind für die jeweils genutzten Verfahren nötig. WordNet und Übersetzung
unterstützen hier DE/EN, OpenThesaurus nur DE; Sprachen dafür explizit angeben.
WordNet sucht gemeinsame englische Synsets, OpenThesaurus gemeinsame deutsche
Synonymgruppen. Beide liefern binäre Evidenz, keine Wahrscheinlichkeiten.
Unbekannt ergibt 0, auch bei identischen unbekannten Labels. Nicht transitive Suche;
Wortmehrdeutigkeit bleibt ohne Kontext ungelöst. Eigene Lexikonpfade sind über
`config.lexicons` möglich. Lokale Daten liegen unter `.cache/lexicons/`.

Lemmatisierung braucht spaCy-Modelle, Stemming keinen Korpusdownload.
Kompositazerlegung ist eine einfache DE-Heuristik mit OpenThesaurus-Wortliste.
Stopword Removal kann Negation entfernen. Beide sind bewusst Ablationen.

## Forschung: ein Vergleichslauf

```bash
PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
.venv/bin/python -m research.compare \
  --models --lexicons --output results/vergleich.json
```

Ohne `--models`/`--lexicons` werden nur die übrigen Verfahren verglichen.
`--preprocessing normalize lowercase` beschränkt den Lauf auf diese Schritte;
`--preprocessing` allein verwendet Rohtexte. Ohne diese Option laufen alle
Preprocessing-Vergleiche. Das frühere `--extended` wird noch akzeptiert, hat aber
keine Wirkung mehr: Es gibt keinen zweiten Vergleichsmodus.

**Änderungen an Experimenten:** In `research/compare.py` stehen `PIPELINES`
und `configurations()`. Letzteres erzeugt die flache Konfigurationsliste aus
Einzelmethoden, Kombinationen, Gewichten und Preprocessing. Die Dictionaries
verwenden dieselben `methods` und `combiner` wie der Service. Neue Kombinationen
dort ergänzen; neue Rechenregeln in `src/synonym_matching/combinations.py`. Neue Similarity-Funktionen
können zunächst in der Forschung erprobt und später in `methods.py` registriert
werden. `DEFAULT_METHODS` bleibt unabhängig von neu registrierten Verfahren.

Die bestehenden 164 Konfigurationen vergleichen mit allen Ressourcen 38 Szenarien:
28 ursprüngliche Kategorien und sechs zusätzliche schwierige Kontrastkategorien.
Testdaten mit erwarteten Paarzuordnungen stehen in `research/model-cases.json`;
`python -m research.build_model_cases` erzeugt sie aus dem Repository-Beispielmodell
und synthetischen Varianten. `examples/order-management-input.json` ist eine
Serviceeingabe mit Labels dieses Modells. Reale geprüfte Schülerabgaben fehlen.

Ein Lauf speichert **eine JSON** (Formatversion 2), keine Markdown-Berichte: Dataset, Konfigurationen,
Rohscores, kombinierte Matrizen, Entscheidungen, Precision/Recall/F1, Top-1,
Laufzeiten, Seed 42, Modellrevisionen, Ressourcen-/Codehashes und Paketversionen.
Bestehende Dateien werden nicht überschrieben. Nicht unterstützte Sprachen werden
als nicht verfügbar markiert; technische Fehler führen zu Exitcode 1.

Top 3 je Kategorie und insgesamt erscheinen im Terminal und unter `rankings` im
JSON. Preprocessing und Einzelmethoden werden ausgeschrieben. Auf gespeicherten
Ergebnissen ohne erneute Modellberechnung:

```bash
PYTHONPATH=src python -m research.rank_results --input results/vergleich.json
```

Das ergänzt Rankings in derselben JSON. `--strategy mutual_best` oder `hungarian`
wählt eine andere bereits berechnete Zuordnung; `--output neue-datei.json` schreibt
optional eine vollständige Kopie. Die Formatierung liegt in `rank_results.py`.

## Grenzen der Auswertung

- Kombinationen begrenzen Roh-Cosinus [-1,1] auf [0,1]. String-, Cosinus- und
  Lexikonwerte sind dadurch nicht kalibriert. Rohscore-Verteilungen bleiben im JSON.
- Fester Threshold 0,5, kein Tuning auf Testantworten. Rankings sind explorativ.
  Micro-F1, dann Precision und Recall; reine Negativfälle nach korrekter Ablehnung.
  Gleichstände werden gekennzeichnet. Leere Mengen sind keine Qualitätserfolge.
- Gesamtvergleiche zeigen getrennt vollständige Abdeckung und gemeinsame Fallmengen.
  Einzelpaare ergeben oft Gleichstände. Größere Matrizen beeinflussen Micro-F1 stärker.
- Top-1 betrachtet die ungefilterte Rangliste bei mehreren Kandidaten. Mutual Best
  behält Gleichstände. Hungarian maximiert die zugelassenen Scores mit Nichtzuordnung
  und höchstens 1:1; unter Threshold liegende Kanten sind vorher gesperrt.
  SciPy verwendet einen Jonker-Volgenant-Solver. Mehrere annotierte korrekte Alternativen
  können deshalb bei 1:1 den Recall senken, ohne dass die gewählte Zuordnung falsch ist.
- Geteilte Featurezeiten inklusive Erstladen/Cacheeffekten sind keine isolierten
  End-to-End-Messungen; Kandidatenaufbau und JSON-Konvertierung sind ausgeschlossen.
- „Bank/Bank“ mit verschiedener Bedeutung bleibt ohne Kontext unlösbar. Die
  Kandidatenheuristik nutzt Konkurrenz in der Matrix, keine Graphstruktur.
- Stacking, TF-IDF und Wortvektoren bleiben zurückgestellt. Lernende Verfahren
  brauchen unabhängige, nach Aufgaben gruppierte Trainings-/Validierungs-/Testdaten.

## Docker und Tests

Im Serviceverzeichnis:

```bash
docker build -t modeling-copilot/synonym-matching:0.1.1 .
docker run --rm --network none -i modeling-copilot/synonym-matching:0.1.1 < examples/order-management-input.json
python -m pytest -q
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 RUN_MODEL_TESTS=1 RUN_LEXICON_TESTS=1 python -m pytest -q
```

Das Image lädt Abhängigkeiten, Standardmodelle, DE/EN-spaCy-Modelle und Lexika beim
Build. Ein Container verarbeitet eine Eingabe und endet. Daten bleiben im Image,
RAM-Caches nur im Prozess. Andere Modelle benötigen ein entsprechend vorbereitetes
Image. Modellrevisionen stehen standardmäßig auf `main`, geladene Revisionen werden
in Experimenten dokumentiert. Die Dagu-Datenübergabe ist weiterhin Demo-Stand und
muss vom aufrufenden Dienst angepasst werden.

Lexikonquellen: [WordNet/NLTK](https://www.nltk.org/howto/wordnet.html),
[WordNet-Lizenz](https://wordnet.princeton.edu/license-and-commercial-use),
[OpenThesaurus](https://www.openthesaurus.de/about/download/api).
OpenThesaurus bietet CC BY-SA 4.0 oder LGPL; Lizenzhinweise werden mit heruntergeladen.

## Übergabe für die Anbindung

Der Aufrufer startet den Container mit dem oben beschriebenen JSON über stdin oder
`TEMPLATE_INPUT`. Er liest genau ein Objekt mit `synonymMatrix` aus stdout und
prüft den Exitcode; Fehlerdetails stehen auf stderr. Es ist kein HTTP-Endpunkt
nötig. Die IDs und Sprachangaben müssen aus den Modelllabels übernommen werden.

Zum Testen eines semantischen Verfahrens kann der Aufrufer ausdrücklich
`"config": {"methods": ["multilingual"]}` setzen. Der unveränderte Standard ist
weiterhin die String-Baseline, keine automatisch ausgewählte beste Pipeline.
Die später gewünschte Kombination lässt sich über dieselbe Konfiguration wählen.

Die öffentlichen Aufrufe `from synonym_matching import match, MatchingEngine`
bleiben erhalten. Interne Importe aus `engine`, `variants` und `combiners` wurden
auf `service` bzw. `combinations` zusammengeführt. Der neue Forschungsbefehl ist
`python -m research.compare`; ältere Ergebnis-JSONs bleiben mit `rank_results`
auswertbar. Die Dagu-Datenübergabe ergänzt der aufrufende Dienst.
