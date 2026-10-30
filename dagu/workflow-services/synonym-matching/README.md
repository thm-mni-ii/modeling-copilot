# Synonym Matching

Zwei Listen von Modelllabels hinein, eine Synonymmatrix mit IDs, Labels,
Einzelscores und Combined Score heraus. Keine HTTP-API oder Datenbank;
die Anbindung übernimmt der aufrufende Dienst.

## Start

Mit aktivierter lokaler Python-3.12-Umgebung:

```bash
pip install -r requirements.txt
python src/main.py --input examples/order-management-input.json
```

Alternativ liest die CLI JSON aus `TEMPLATE_INPUT` oder stdin. Die Ausgabe ist
ein JSON-Objekt mit `synonymMatrix`. Fehler: stderr und Exitcode 1.
Die Dockerdatei ist noch der Skeleton-Stand und installiert keine Abhängigkeiten;
Containeranbindung ist eine separate Aufgabe.

## Eingabe und Ausgabe

```json
{
  "step": "synonym_matching",
  "input": {
    "referenceModel": {"elements": [{"id": "r1", "label": "Kunde", "language": "de"}]},
    "studentModel": {"elements": [{"id": "s1", "label": "Kund", "language": "de"}]},
    "config": {"methods": ["levenshtein"], "combiner": {"kind": "mean"}}
  }
}
```

```json
{
  "synonymMatrix": [{
    "referenceElement": {"id": "r1", "label": "Kunde", "language": "de"},
    "matches": [{
      "submissionElement": {"id": "s1", "label": "Kund", "language": "de"},
      "scores": {"levenshtein": 0.8},
      "combinedScore": 0.8
    }]
  }]
}
```

Ohne `input.threshold` bleiben alle nichtleeren Kandidaten enthalten. Ein Threshold
filtert nach `combinedScore >= threshold`. Kandidaten sind absteigend sortiert;
Gleichstände behalten die Eingabereihenfolge. Keine erzwungene 1:1-Zuordnung.
Erst zur Ausgabe werden Scores auf vier Nachkommastellen gerundet. Berechnung,
Sortierung und Threshold behalten volle Genauigkeit. Roh-Cosinus liegt in [-1,1];
vor Kombination werden Scores auf [0,1] begrenzt.

Leere Mengen sind erlaubt. Leere Labels ergeben intern Score 0 und keine Kandidaten.
Doppelte Labels mit verschiedenen IDs bleiben getrennt; doppelte IDs innerhalb
einer Seite sind ungültig. Original-IDs und Labels bleiben erhalten.
Die CLI verarbeitet bereits extrahierte Labels, kein Graph-XML.

## Verfahren und Aufbau

- `main.py`: JSON einlesen und Synonymmatrix ausgeben.
- `engine.py`: Preprocessing, Score-Berechnung und Kombination koordinieren.
- `methods.py`: Levenshtein, Damerau-Levenshtein, Jaro-Winkler, Zeichen-n-Gramme,
  Token-Jaccard, Token Sort Ratio, Wortreihenfolge, Exact Match, übersetzte Strings
  und beide Embedding-Pfade.
- `variants.py`: 15 feste Variantenfunktionen: String-/Token-Ensembles,
  Embedding-Kombinationen, String/Embedding-Hybride, gewichtete Fusion, Maximum,
  geometrisches Mittel, Exact-Match-Regel und Kandidatenheuristik.
- `combiners.py`: Mean, Max und Weighted Mean.
- `preprocessing.py`, `translation.py`, `cache.py`: Textvorbereitung und
  Wiederverwendung von Embeddings/Übersetzungen pro eindeutigem Label im RAM.
- `config.py`: Konfiguration prüfen.
- `evaluation.py`: kleine Auswertung erwarteter Zuordnungen, kein Training.

Die Kandidatenheuristik (`context_aware`) wertet Konkurrenz innerhalb der Matrix
aus, keine Graphstruktur oder Wortbedeutung im Aufgabenkontext.

```python
from synonym_matching import MatchingEngine
from synonym_matching.variants import REQUIRES

name = "string_ensemble"
engine = MatchingEngine({
    "methods": list(REQUIRES[name]),
    "preprocessing": ["normalize", "lowercase"],
    "combiner": {"kind": "variant", "name": name},
})
result = engine.match(["Kunde"], ["Kund", "Lieferant"])
```

Intern stellt die Engine vollständige Score-Matrizen für die Wiederverwendung
zwischen Varianten bereit; die CLI gibt nur `synonymMatrix` aus.
`examples/functions.py` zeigt direkt kombinierbare Funktionen.

## Preprocessing und Modelle

Geordnete Schritte: `normalize`, `split_identifiers`, `lowercase`, `lemmatize`,
`stem`, `remove_stopwords`; `[]` deaktiviert Preprocessing. String-Preprocessing
und `embedding_preprocessing` sind separat konfigurierbar. Engine-Standard ist
nur Normalisierung. Stopword Removal kann Negation entfernen.

- Multilingual: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
- Monolingual: `sentence-transformers/all-MiniLM-L6-v2` nach
  `Helsinki-NLP/opus-mt-de-en` (DE→EN; Englisch bleibt unverändert).
- Modelle sind über `config.embedding` austauschbar. Der erste Aufruf kann
  Modellgewichte herunterladen. Übersetzung verlangt explizite `de`/`en`-Angaben;
  Spanisch ist nur im direkten multilingualen Pfad unterstützt.
- Lemmatisierung benötigt `de_core_news_sm`/`en_core_web_sm`. Stemming braucht
  NLTK, aber keinen zusätzlichen Korpusdownload.

## Testfälle vergleichen

`examples/order-management-input.json`: neun Labels der Repository-Musterlösung
und synthetisch veränderte Schülerlabels mit ursprünglichen IDs.
`examples/model-cases.json`: alle 28 Kategorien; Kategorie 28 hat fünf Unterfälle,
ursprünglich 32 Szenarien mit vollständigen Paarannotationen; erweitert sind es 38.

```bash
PYTHONPATH=src python examples/check_model_cases.py --output results/vergleich.json
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONPATH=src python examples/check_model_cases.py --models --output results/vergleich-modelle.json
```

Nur zwei Dateien entstehen:

- JSON: ungefilterte Synonymmatrizen je Einzelmethode und verfügbarer Variante.
- Markdown: TP/FP/FN, Precision/Recall/F1, Graph-Top-1 und Ergebnis je Testfall.

`--models` aktiviert beide Embedding-Pfade und Kombinationen. Basisscores werden
pro Fall einmal berechnet und wiederverwendet. Offline-Variablen verlangen bereits
lokal vorhandene Modelle. `--threshold 0.5` betrifft nur die Auswertung; Matrizen
bleiben vollständig. Es gibt keine Threshold-Optimierung.
`--preprocessing normalize lowercase` wählt Schritte; `--preprocessing` allein
verwendet Rohtexte. Embeddings bleiben dabei minimal normalisiert.

Nicht unterstützte Sprachen und Fehler stehen am Eintrag (`synonymMatrix: null`).
Technische Fehler ergeben Exitcode 1, fachliche Fehlzuordnungen sind Ergebnisse.
Bestehende Ausgabedateien werden nicht überschrieben. Die Auswertung verwendet
ungerundete Scores.

Annotationen sind synthetische Erwartungen, keine unabhängige Qualitätsbestätigung.
„Auftrag erteilen“ wird hier als Bestellvorgang aufgefasst; das ist kontextabhängig.
„Bank/Bank“ mit verschiedenen Bedeutungen bleibt eine Grenze des Labelvergleichs.
Top-1 bei Einzelpaaren ist trivial, der Graphfall wird separat ausgewiesen.
Spanische Fälle nicht mit dem auf DE/EN beschränkten Übersetzungspfad gleichsetzen.
Leere Mengen zählen nicht als Qualitätserfolge. Reale, geprüfte Abgaben fehlen noch.

`python examples/build_model_cases.py` erzeugt die Beispiele aus dem unveränderten
Repository-Graphen neu. Kein zusätzlicher Schülergraph wird gespeichert.

## Tests

```bash
python -m pytest -q
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 RUN_MODEL_TESTS=1 python -m pytest -m integration -v
```

Tests sichern Schnittstelle, IDs, Matrizen, Sonderfälle, Caching und Auswertung ab;
sie behaupten keine perfekte semantische Trefferquote.

## Zurückgestellt

Stacking (Logistic Regression, Random Forest), ElasticNet, SVR, neuronales Stacking,
Wortvektor-, Syntax- und TF-IDF-Verfahren sind mögliche Erweiterungen,
aber nicht im aktiven Service. TF-IDF braucht einen festgelegten Korpus; lernende
Kombinationen benötigen ausreichende gelabelte Daten und saubere Trainings-/
Validierungs-/Testtrennung, gegebenenfalls Out-of-Fold-Features.

Benchmark-Suites, separater Split-Datensatz, CSV-Berichte und Umgebungs-/Quellcode-
protokolle sind entfernt. Alte lokale Ergebnisse bleiben erhalten; neue Läufe
erzeugen nur Matrizen und die kleine Übersicht.

## WordNet und OpenThesaurus

Einmalig die lokalen Daten vorbereiten (NLTK steht in `requirements.txt`):

```bash
python examples/download_lexicons.py
```

Die Daten liegen unter `.cache/lexicons/` und werden nicht in Git aufgenommen.
Beim Matching gibt es keine Lexikon-Downloads oder API-Aufrufe.

- **`wordnet`**: Deutsche Labels werden über den vorhandenen DE→EN-Übersetzer
  übersetzt, englische unverändert verwendet. Score 1 bei einem gemeinsamen
  englischen Synset, sonst 0. NLTK berücksichtigt dabei Wortformen. Ganze Phrasen
  werden als WordNet-Eintrag gesucht, nicht durch einzelne Worttreffer ersetzt.
- **`openthesaurus`**: Direkte Abfrage deutscher Labels. Score 1 bei einer gemeinsamen
  Synonymgruppe, sonst 0. Keine Übersetzung, keine transitive Vereinigung von Gruppen.
  Bekannte abschließende Registerangaben wie `(ugs.)` werden im Export entfernt;
  sonstige Klammerausdrücke bleiben erhalten. Keine automatische Flexionsanalyse.
- Beide normalisieren Leerraum/Unicode und Kleinschreibung für die Suche.
  Ein Score 0 heißt „kein gemeinsamer Eintrag“, nicht „sicher kein Synonym“.
  Gleiche unbekannte Labels bekommen ebenfalls 0. Ohne Bedeutungskontext können
  mehrdeutige Wörter fälschlich passen. OpenThesaurus enthält auch Assoziationen.

Auswahl in `input.config`:

```json
{"methods": ["wordnet", "levenshtein"], "combiner": {"kind": "mean"}}
```

Für OpenThesaurus `"methods": ["openthesaurus"]` verwenden. Sprache pro Label
angeben: WordNet unterstützt hier DE/EN, OpenThesaurus nur DE. Original-IDs und
Labels bleiben in der Ausgabe erhalten. Eigene lokale Pfade sind optional über
`config.lexicons.wordnet` (NLTK-Datenverzeichnis) und
`config.lexicons.openthesaurus` (Textdatei) einstellbar.

Mit den vorhandenen Testfällen vergleichen:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONPATH=src python examples/check_model_cases.py --models --lexicons --output results/lexika.json
RUN_LEXICON_TESTS=1 python -m pytest tests/test_lexicons.py -q
```

`--lexicons` fügt beide Einzelverfahren hinzu, auch ohne `--models` (WordNet braucht
für deutsche Labels trotzdem das Übersetzungsmodell). Nicht unterstützte Sprach-
kombinationen werden ausdrücklich als nicht ausgeführt markiert. Deshalb umfasst
OpenThesaurus weniger Fälle; die Gesamtmetriken sind nicht direkt vergleichbar.
Das originale englische Graphbeispiel wird nicht künstlich als deutsches umetikettiert.

Quellen: [WordNet über NLTK](https://www.nltk.org/howto/wordnet.html),
[WordNet-Lizenz](https://wordnet.princeton.edu/license-and-commercial-use),
[OpenThesaurus-Download](https://www.openthesaurus.de/about/download/api).
OpenThesaurus bietet CC BY-SA 4.0 oder LGPL; die Original-Lizenzdatei bleibt beim
Download erhalten. Der verwendete Textdump enthält sein Erstellungsdatum im Kopf.

## Lesereihenfolge für die Codekontrolle

1. `src/main.py`: Wo kommen die zwei Listen her, was wird ausgegeben?
2. `src/synonym_matching/engine.py`: Gesamtablauf in `MatchingEngine.match()`.
3. `preprocessing.py`, `methods.py`, `lexicons.py`: Wie entsteht ein Einzelscore?
4. `combiners.py`, `variants.py`: Wie werden Einzelscores kombiniert?
5. `examples/check_model_cases.py`, `evaluation.py`: Wie werden Fälle verglichen?
6. `config.py`, `cache.py`, `translation.py`: Einstellungen und Wiederverwendung.

Kommentare und Docstrings erklären Zweck, Eingaben und wichtige Sonderfälle.
NumPy bleibt für Score-Matrizen erhalten; die Zeilen sind Referenzlabels und die
Spalten Schülerlabels. Modellbibliotheken werden bewusst erst bei Bedarf importiert
und geladen, damit reine Stringvergleiche ohne Modellgewichte laufen können.

## Erweiterte Experimente (Service-API unverändert)

Bestandsprüfung: Drei Varianten waren Aliase für Einzelmethoden; die bisherige
50:50-Fusion war ebenfalls doppelt. Im Vergleichskatalog sind diese entfernt,
die vorhandenen Funktionen bleiben für Aufrufer verfügbar. Es gibt keine
nachträgliche Deduplizierung anhand zufällig gleicher Testergebnisse.

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONPATH=src python examples/check_model_cases.py --extended --models --lexicons --output results/erweitert.json
```

Der erweiterte Lauf erzeugt wieder nur JSON und Markdown. Anders als die normale
Matrixansicht enthält dieses JSON auch ungerundete Rohscores, Auswahlmasken,
Metriken, Dataset, Pipelineparameter, Seed, Modellrevisionen, Ressourcen-/Codehashes
und Paketversionen. Bestehende Ergebnisse werden nicht überschrieben. Die CLI des
Services (`src/main.py`) und ihr Ein-/Ausgabeschema bleiben unverändert.

**Preprocessing:** Rohtexte, Normalisierung, Lowercase, Lemmatisierung, Stemming,
Identifier-Trennung und Kompositazerlegung werden separat verglichen. Nur die
String-/Token-Pfade ändern sich. Embeddings, Übersetzung und Lexika verwenden feste
minimale Normalisierung und werden nicht für identische Einstellungen wiederholt.
Eine Stemming-Ausgabe wird insbesondere nicht in das Übersetzungsmodell geschickt.

Lemmatisierung benötigt die lokalen spaCy-Modelle `de_core_news_sm==3.8.0` und
`en_core_web_sm==3.8.0`. Die Komposita-Ablation verwendet vorhandene deutsche
OpenThesaurus-Einträge als Wortliste, sucht zwei bekannte Bestandteile und erlaubt
Fugenelemente. Sie ist bewusst eine einfache Heuristik: keine handgeschriebene
Liste der Testantworten, keine vollständige morphologische Analyse. Falsche
Zerlegungen sind möglich. Englisch bleibt dabei unverändert. Identifier-Trennung
ist ein eigener Vergleich und wird nicht als deutsche Kompositazerlegung verkauft.

**Gewichte und Hybride:** String-Ensemble : multilinguales Embedding mit 25:75,
50:50 und 75:25. WordNet bzw. OpenThesaurus jeweils mit String-Ensemble oder
multilingualem Embedding (50:50); zusätzlich Mean(WordNet, OpenThesaurus).
Lexikonwert 0 heißt fehlende Evidenz, kann im Mittelwert aber einen guten anderen
Score herabsetzen. Genau diese Wirkung ist Teil des Vergleichs.

**Score-Vergleichbarkeit:** Alle Kombinationsscores liegen in [0,1]. Cosinus wird
wie bisher aus [-1,1] auf [0,1] begrenzt, nicht linear verschoben. Das macht die
Scores numerisch kombinierbar, aber nicht zu kalibrierten Wahrscheinlichkeiten.
Die Auswertung speichert Min/Max/Mittel, Null-/Einsanteil und negative Rohscores.
Keine Min-Max-Skalierung pro Testmatrix. Der Threshold bleibt vorab fest bei 0,5;
keine Aussage, dass er für alle Verfahren optimal wäre.

**Zuordnung:** Jede Score-Matrix wird unverändert mit Threshold, Mutual Best und
Hungarian verglichen. Mutual Best lässt alle Gleichstände zu, also ggf. mehr als
eine Zuordnung. Hungarian maximiert die Summe zugelassener Scores mit Dummy-Spalten
für Nichtzuordnung. Kanten unterhalb des Thresholds werden vor der Optimierung
gesperrt; Scores von 0 liefern keine Zuordnung. SciPy verwendet dafür einen
Jonker-Volgenant-Solver für dasselbe lineare Zuordnungsproblem, keine eigene
Implementierung des historischen Hungarian-Algorithmus.

IDs verschiedener Seiten dürfen gleich sein. Leere Mengen, rechteckige Matrizen,
fehlende Entsprechungen und doppelte Labels bleiben erlaubt. Bei gleichwertigen
Lösungen hängt die 1:1-Auswahl von Reihenfolge/Solver ab; beides wird festgehalten.
Unsere Annotationen erlauben mehrere korrekte Kandidaten: Ein Recall-Abfall durch
1:1 bedeutet deshalb nicht automatisch eine fachlich falsche Zuordnung.

**Auswertung:** Precision, Recall, F1, Top-1 und Laufzeit. Top-1 bewertet die
Score-Rangliste bei mehreren Kandidaten und ändert sich nicht durch die spätere
Zuordnung. Die Übersicht verwendet gemeinsame Fallmengen, damit fehlende
Sprachunterstützung keine Variante bevorzugt. Ein zusätzlicher Kernvergleich ohne
OpenThesaurus erhält die DE/EN-Fälle einschließlich Übersetzungen und Graphbeispiel.
Alle Ergebnisse und Abdeckungsgrenzen je Fall bleiben im JSON.

Featurezeiten werden zwischen Kombinationen geteilt. Die Summe dieser Zeiten ist
keine isolierte End-to-End-Messung; Erstladen und RAM-Cacheeffekte sind enthalten.
Kombinations- und Zuordnungszeit werden separat gemessen. Laufzeiten sind nicht
bitgenau reproduzierbar und hardwareabhängig.

Sechs zusätzliche schwierige Kontrastmengen prüfen Negation, aktiv/inaktiv,
vertauschte Rollen, Statusunterschiede, Oberbegriffe und ähnliche Komposita. Damit
sind es 34 Kategorien / 38 Szenarien. Alle Erwartungen bleiben synthetisch und
bedürfen fachlicher Validierung; Ergebnisse sind vorläufig und kein Testset für
nachträgliches Tuning.

**Optionales Stacking:** Logistic Regression ist weiterhin zurückgestellt, weil
kein unabhängiger, gruppierter Trainings-/Validierungs-/Testdatensatz vorliegt.
Die Varianten derselben Aufgabe würden bei einem zufälligen Paarsplit leaken.
Es wird kein Modell auf den hier ausgewerteten Testantworten trainiert.
