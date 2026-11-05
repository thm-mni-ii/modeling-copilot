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

Für diesen Python-Aufruf `PYTHONPATH=src` setzen. Ohne explizite Methodenauswahl gilt jetzt die vorläufige semantische Pipeline:

```python
# In src/synonym_matching/config.py als DEFAULT_CONFIG festgelegt:
{
    "methods": ["levenshtein", "jaro_winkler", "char_trigram", "multilingual"],
    "preprocessing": ["normalize"],
    "embedding_preprocessing": ["normalize"],
    "combiner": {"kind": "variant", "name": "weighted_fusion",
                 "options": {"embedding_weight": 0.5}},
}
```

Combined Score = 50 % Mittel(Levenshtein, Jaro-Winkler, Zeichen-Trigramme)
+ 50 % multilinguales Embedding. Kein Lowercasing, keine Übersetzung, kein Lexikon.
Der Modellpfad ist `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
Damit funktioniert der Standard auch ohne explizite DE/EN-Sprachangaben.

Auswahlgrundlage: `vergleich-vereinfacht.json`, Threshold 0,5, 35 auswertbare
synthetische Szenarien mit voller Sprachabdeckung: Precision 0,714, Recall 0,745,
F1 0,729 (14 FP, 12 FN). Diese Pipeline ist gemeinsam mit der Exakt-Regel vorne;
die zusätzliche Regel wird für den ersten Lauf nicht benötigt. Die DE→EN-Variante
mit F1 0,773 deckt nur 33 Szenarien ab und ist deshalb kein direkt vergleichbarer
Gesamtsieger. Keine Aussage über geprüfte reale Schülerabgaben und kein Training.
Die Umstellung erfolgt manuell; neue Forschungsläufe ändern DEFAULT_CONFIG nicht.

Eine explizite Liste `config.methods` ersetzt die Pipeline vollständig; ohne
expliziten `combiner` gilt dann wie bisher der einfache Mittelwert dieser Methoden.
Die ursprünglichen fünf Stringverfahren bleiben als `STRING_BASELINES` in
`methods.py` verfügbar. Der Threshold bleibt optional und wird nicht automatisch
auf 0,5 gesetzt. Für dieselbe Filterung wie im Vergleich `input.threshold=0.5`
übergeben. Ausgabeformat und IDs bleiben unverändert. Der Standard braucht jetzt
das vorbereitete multilinguale Modell (im Docker-Image bereits enthalten).

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
werden. `DEFAULT_CONFIG` bleibt unabhängig von neu registrierten Verfahren.

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

Ohne `input.config` verwendet der Container die oben dokumentierte 50:50-Pipeline.
`"config": {"methods": ["multilingual"]}` wählt stattdessen nur das Embedding;
`"config": {"methods": ["levenshtein"]}` nur die Stringmetrik.
Explizite bisherige Konfigurationen behalten ihre Wirkung.

Die öffentlichen Aufrufe `from synonym_matching import match, MatchingEngine`
bleiben erhalten. Interne Importe aus `engine`, `variants` und `combiners` wurden
auf `service` bzw. `combinations` zusammengeführt. Der neue Forschungsbefehl ist
`python -m research.compare`; ältere Ergebnis-JSONs bleiben mit `rank_results`
auswertbar. Die Dagu-Datenübergabe ergänzt der aufrufende Dienst.

## Neue Forschungsvarianten 21–32

Diese Erweiterungen liegen ausschließlich unter `research/`. Service-Standard,
Schnittstelle, Docker-Abhängigkeiten und bestehende Vergleiche bleiben erhalten.

| Nr. | Umsetzung |
| --- | --- |
| 21 | Word2Vec + Greedy-1:1-Wort-Matching |
| 22 | FastText + dasselbe Wort-Matching |
| 23 | FastText-Wort-Matching + Levenshtein, je 50 % |
| 27 | Gewichtete Fusion der GloVe-, FastText- und Paragram-Wort-Matching-Scores; zunächst gleiche Gewichte |
| 30 | 50:50-String/Embedding-Hybrid + Zeilen-/Spaltenrang-Fusion |
| 32 | Nr. 22 mit vorhandenem Hungarian-Assignment auf der Labelmatrix; keine zweite FastText-Berechnung |

Aktivierung (noch ohne neue Ressourcen):

```bash
PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
.venv/bin/python -m research.compare --models --lexicons --new-methods \
  --output results/vergleich-neue-methoden.json
```

Fehlende Vektoren ergeben **nicht verfügbar**, keine erfundenen
Scores oder Qualitätserfolge.
Ohne `--new-methods` bleibt der bisherige Katalog von 164 Konfigurationen erhalten.

### Wort-Matching und Vektoren

`research/word_matching.py` implementiert die gepostete Paper-Regel:
Wortpaar mit höchstem Score wählen, Zeile und Spalte entfernen, wiederholen.
Dann `(Summe + |m-n| * delta) / max(m,n)`, standardmäßig `delta=0.2`.
Das ist greedy, nicht global optimal. Gleichstände folgen der Tokenreihenfolge.
Wörter werden als Menge ohne Wiederholungen verwendet. Das Wort-Matching und
Hungarian auf der gesamten Labelmatrix sind zwei unterschiedliche Ebenen.

Beidseitig leere Wortmengen erhalten 0; einseitig leer ergibt laut Formel delta.
Original leere Labels bleiben entsprechend der Servicekonvention 0 und werden
nicht zu Kandidaten. Unbekannte Wörter bleiben in der Wortanzahl, erhalten aber
keine erfundene Vektorevidenz. Wort-Cosinus wird vor dem Matching auf [0,1]
begrenzt. Ressourcenpfade, Optionen und Dateihashes stehen im Ergebnis.

Vortrainierte Vektoren selbst bereitstellen; es wird nichts automatisch trainiert
oder heruntergeladen. Konfigurationsvorlage: `research/word-vectors.example.json`.
Pfade beziehen sich auf das Serviceverzeichnis. Nur vorhandene Modelle eintragen.
Für reine Vektordateien wird Gensim bei Bedarf importiert; vollständige
FastText-Binärmodelle nutzen den nativen FastText-Loader:

```bash
.venv/bin/python -m pip install gensim==4.4.0 fasttext==0.9.3
```

Unterstützt: `word2vec_text`, `word2vec_binary`, `fasttext_bin` (mit Subwords),
`glove` (Text ohne Header). Die kleinen Vektoren der Tests prüfen nur die
Funktion und sind kein Qualitätsbenchmark.
FastText-Textvektoren enthalten keine Subword-Informationen; nur ein vollständiges
FastText-Binärmodell kann unbekannte Wörter über Subwords repräsentieren.

Getrennte Sprachdateien müssen im selben ausgerichteten Raum liegen und benötigen
`aligned: true`. Gleiche Dimension allein reicht nicht. Alternativ übersetzt
`translate_to_en: true` DE→EN vor dem Zugriff auf englische Vektoren; andere
Sprachen werden dabei nicht unterstützt. Englische Labels bleiben unverändert.
Die Übersetzung wird über die Modelle hinweg wiederverwendet.

Optionen je Modell: `preprocessing` (Standard: normalize, split_identifiers),
`lowercase` (Standard true), `nouns_only` (Standard false), `delta` (Standard 0.2).
Nomenfilterung nutzt die vorhandenen DE/EN-spaCy-Modelle und kann als eigene
Ablation in einem separaten Lauf aktiviert werden. Bei Übersetzung wird POS im
englischen Zieltext bestimmt. Für einen fairen Vergleich die Vorverarbeitung
zwischen Vektormodellen gleich halten. Die vollständigen Optionen werden gespeichert.

```bash
PYTHONPATH=src .venv/bin/python -m research.compare --models --new-methods \
  --word-vectors research/meine-wortvektoren.json --output results/wortvektoren.json
```

Modellgröße/RAM-Bedarf, Quelle und Lizenz vor dem Download prüfen. Eigene Felder
wie `model`, `source` und `license` werden mit der Ressourcenkonfiguration gespeichert.
Quellen: [Gensim-Vektorformate](https://radimrehurek.com/gensim/models/keyedvectors.html),
[FastText-Binärmodelle](https://radimrehurek.com/gensim/models/fasttext.html),
[ausgerichtete FastText-Sprachräume](https://fasttext.cc/docs/en/aligned-vectors).

### Globales Ranking

Nr. 30 ist eine ausdrücklich eigene Rangheuristik: Originalscore mal
`2/(Zeilenrang + Spaltenrang)`, mittlere Ränge bei Gleichständen. Sie erhöht keine
schwachen Scores und erzwingt kein 1:1. Anschließende Threshold-/Mutual-Best-/
Hungarian-Auswahl bleibt separat vergleichbar. Keine Nachbildung einer nicht
vorliegenden Paper-Architektur und keine Aussage über eine verbesserte Qualität.

### Lokaler Vergleich mit vortrainierten Vektoren

Für den ersten Lauf wurden lokal folgende englische 300D-Vektoren bereitgestellt:
`word2vec-google-news-300`, `fasttext-wiki-news-subwords-300` (statischer Export),
`glove-wiki-gigaword-300` und `Paragram-SL999-300`. Deutsche Labels werden vorher
mit dem vorhandenen Übersetzungsmodell ins Englische übersetzt. Alle vier Pfade
verwenden `normalize`, `split_identifiers`, danach Übersetzung und Lowercasing;
kein Nomenfilter, `delta=0.2`. Die Fusion nutzt gleiche Gewichte, Threshold 0.5.
Spanische Fälle sind für diese Pfade nicht verfügbar und werden bei einem
gemeinsamen Vergleich ausgeschlossen. Das ist ein synthetischer Diagnoselauf,
kein unabhängiger Nachweis der besten Pipeline.

Die lokalen Pfade und Quellen stehen in `.cache/word-vectors/english-pretrained.json`;
Modellnamen, Optionen und SHA256-Dateihashes werden im Ergebnis gespeichert.
Modelle werden nacheinander geladen und nach der Rohscoreberechnung freigegeben.
Wortmodelle laufen vor den Sentence-Embeddings. Der native FastText-Loader
vermeidet Gensims zusätzliche Matrixkopien und die vorberechneten Vektoren für
den gesamten Wortschatz; abgefragt werden nur die benötigten Wörter.
Ungültige UTF-8-Bytes in einzelnen Vokabelschlüsseln werden beim Einlesen durch
das Unicode-Ersatzzeichen ersetzt; die Vektoren bleiben unverändert.

```bash
PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
.venv/bin/python -m research.compare --models --lexicons --new-methods \
  --word-vectors .cache/word-vectors/english-pretrained.json \
  --output results/vergleich-wortvektoren.json
```

Für einen erneuten Lauf einen neuen Ausgabedateinamen wählen. Modelle und Ergebnisse
bleiben lokal und sind nicht im Docker-Image enthalten. Die Wortvektoren stammen
aus [Gensim Data](https://github.com/piskvorky/gensim-data) bzw.
von [John Wieting](https://www.cs.cmu.edu/~jwieting/). Für Google-News-Vektoren nennt
die Gensim-Metadatei keine Lizenz; eine Weiterverteilung ist damit nicht geklärt.

Erster Lauf: `results/vergleich-wortvektoren.json`, 183 Konfigurationen, keine
technischen Fehler. Die 6.038 verfügbaren Ergebnisse des bisherigen Katalogs
behalten ihre Scores und Zuordnungen (Scoretoleranz 1e-7).
Die folgende Vorauswahl vergleicht **dieselben 33 nichtleeren Szenarien**:
alle aus `research/model-cases.json` außer den spanischsprachigen Fällen 11 und 22
und den technischen Fällen ohne gültiges Labelpaar. Threshold ist 0.5.

| Pipeline | Precision | Recall | F1 | Top-1 |
| --- | ---: | ---: | ---: | ---: |
| Bisheriger Service: normalize + String/Multilingual 50:50 | 0.702 | 0.767 | 0.733 | 0.741 |
| normalize + derselbe Hybrid + globales Ranking | 0.775 | 0.721 | 0.747 | 0.741 |
| Word2Vec + Wort-Matching | 0.635 | 0.767 | 0.695 | 0.704 |
| FastText + Wort-Matching | 0.500 | 0.814 | 0.619 | 0.741 |
| lowercase + FastText-Wort-Matching/Levenshtein 50:50 | 0.667 | 0.791 | 0.723 | 0.815 |
| GloVe/FastText/Paragram gleich gewichtet | 0.654 | 0.791 | 0.716 | 0.741 |
| Bestehender Vergleich: lowercase + String/Übersetzungs-Embedding 50:50 | 0.756 | 0.791 | 0.773 | 0.815 |

Top-1 zählt nur Referenzlabels mit korrekter Entsprechung und mehreren Kandidaten;
es bewertet die Rangliste vor der Zuordnungsfilterung. Bei FastText erhöht
Hungarian den F1 von 0.619 auf 0.682; Mutual Best erreicht 0.753.
Die Dreifachfusion erreicht mit Mutual Best 0.810 und mit Hungarian 0.779;
dieselben Filter sind deshalb auch mit den bisherigen Verfahren zu vergleichen.
Der bisherige Übersetzungs-Hybrid erreicht beispielsweise mit Mutual Best 0.835.
Das sind keine getrennt optimierten oder unabhängig getesteten Modelle.

FastText allein liefert in diesen Daten viele falsche Treffer für verwandte
Begriffe, Antonyme und Oberbegriffe. Globales Ranking reduziert falsche Treffer,
übersieht aber auch mehr korrekte. Im Graph-Label-Fall 21 erzielt keine dieser
Varianten alle richtigen Zuordnungen. Die Servicepipeline bleibt vorerst erhalten.

Der Gesamtlauf benötigte rund 505 Sekunden einschließlich Laden der Modelle.
Das erstmalige Laden der Wortvektoren dauerte etwa 15 s (Word2Vec), 154 s
(FastText), 62 s (GloVe) und 256 s (Paragram). Geteilte Features und Caches machen
die gespeicherten Featurezeiten nicht zu unabhängigen End-to-End-Laufzeiten je
Pipeline; warme Service-Latenzen lassen sich daraus nicht ableiten.

### Geplanter Sprachvergleich: Modelle von Hugging Face

Zwei Konfigurationen verwenden den vorhandenen Forschungsrunner; die Servicepipeline
bleibt unverändert. Die Ressourcen liegen nach dem Download lokal unter
`.cache/word-vectors/` und werden nicht mit Git versioniert.
Die ersten synthetischen Diagnoseläufe sind unten zusammengefasst.

| Konfiguration | Vergleich | Ressourcen |
| --- | --- | --- |
| `research/word-vectors-german.json` | Deutsches Word2Vec und deutsches FastText ohne Übersetzung | Word2Vec ca. 738 MB, FastText ca. 7.24 GB |
| `research/word-vectors-english-hf.json` | DE→EN-Übersetzung + englisches FastText | FastText ca. 7.24 GB |

Word2Vec verwendet den Hugging-Face-Mirror
[Word2vec/german_model](https://huggingface.co/Word2vec/german_model)
des deutschen Müller-Modells. `german.model` hat das Word2Vec-Binärformat.
Die Model Card nennt MIT; die Konfiguration erhält die Groß-/Kleinschreibung.
Eine Lowercase-Ablation sollte als separate Konfiguration mit `lowercase: true`
und eigenem Ergebnisnamen laufen: Großschreibung von Substantiven kann relevant sein.

FastText nutzt die offiziellen Repositories
[facebook/fasttext-de-vectors](https://huggingface.co/facebook/fasttext-de-vectors)
und [facebook/fasttext-en-vectors](https://huggingface.co/facebook/fasttext-en-vectors),
jeweils mit CC BY-SA 3.0. Beide Profile verwenden vollständige Binärmodelle mit
Subword-Unterstützung. Sie unterscheiden sich damit auch vom früher getesteten
statischen englischen Export; dessen Resultate sind ein separater Vergleich.
Auch die Trainingskorpora sind ein Einflussfaktor bei einem Sprachvergleich.

Die beiden monolingualen FastText-Modelle sind nicht automatisch ausgerichtet.
Direkte DE/EN-Cosinusvergleiche zwischen ihnen sind deshalb nicht vorgesehen.
Für ausgerichtete Vektoren wurde keine passende Hugging-Face-Quelle verifiziert;
dieser Versuch ist vorerst zurückgestellt. Der bestehende Loader unterstützt
ausgerichtete lokale Dateien weiterhin. Service-Embeddings und Übersetzer werden
bereits von Hugging Face bezogen.

Ressourcen bei Bedarf einzeln herunterladen; Hugging Face macht große Modelle
nicht kleiner. Zusammen sind es ca. 15.2 GB, zusätzlich wird ausreichend RAM
benötigt. Die Revisionen sind festgelegt und werden mit den Dateihashes im
Ergebnis gespeichert. `hf` ist über das vorhandene `huggingface_hub` verfügbar.

```bash
.venv/bin/hf download Word2vec/german_model german.model \
  --revision 1dfd63ac969f4d0fe5b76eeb20534aa8617d791f \
  --local-dir .cache/word-vectors/word2vec-de
.venv/bin/hf download facebook/fasttext-de-vectors model.bin \
  --revision 2fdd228795139196371a78578790c8191282e25a \
  --local-dir .cache/word-vectors/fasttext-de
.venv/bin/hf download facebook/fasttext-en-vectors model.bin \
  --revision a80392390daaee1a91000da45c376d512e1dc555 \
  --local-dir .cache/word-vectors/fasttext-en
```

Nach Bereitstellung der jeweiligen Dateien:

```bash
PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
.venv/bin/python -m research.compare --models --lexicons --new-methods \
  --word-vectors research/word-vectors-german.json \
  --output results/vergleich-deutsche-wortvektoren.json

PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
.venv/bin/python -m research.compare --models --lexicons --new-methods \
  --word-vectors research/word-vectors-english-hf.json \
  --output results/vergleich-englische-hf-wortvektoren.json
```

Nur identische Fallmengen bei Threshold 0.5 vergleichen: deutsche Modelle und
Übersetzungspipeline auf rein deutschen Mengen; die Übersetzungspipeline kann
zusätzlich gemischte DE/EN-Mengen verarbeiten. Spanisch bleibt hier nicht verfügbar.
Precision, Recall, F1, Top-1 und Laufzeit werden vom vorhandenen Runner gespeichert,
ebenso Modellkonfigurationen und Dateihashes. Word2Vec wird im zweiten Lauf nicht
angegeben; GloVe/Paragram sind in beiden Profilen nicht enthalten. Davon abhängige
Varianten werden nicht als erfolgreich berechnete Vergleiche gewertet.

### Ergebnisse des Sprachvergleichs

`results/vergleich-gesamt-hf.json` vereint 201 Konfigurationen: den bisherigen
Katalog, die neuen deutschen/englischen Modellprofile und eine zusätzliche
Word2Vec-Lowercase-Ablation. Unveränderte Baselines werden einmal übernommen.
Pro neuem Lauf wurden 6.300 bisherige Nicht-Wortvektor-Ergebnisse geprüft:
Scores (Toleranz 1e-7) und Zuordnungen bleiben unverändert. Alle drei neuen Läufe
haben keine technischen Fehler; fehlende Sprach-/Modellabdeckung bleibt markiert.

F1 bei festem Threshold 0.5, ohne Optimierung von Gewichten oder Thresholds:

| Pipeline | 28 rein deutsche Fälle | 33 DE/EN-Fälle |
| --- | ---: | ---: |
| Aktueller Service: normalize + String/Multilingual 50:50 | 0.800 | 0.733 |
| Deutsches Word2Vec + Wort-Matching, Großschreibung erhalten | 0.571 | nicht abgedeckt |
| Deutsches Word2Vec + Wort-Matching, Lowercasing | 0.250 | nicht abgedeckt |
| Deutsches FastText + Wort-Matching | 0.690 | nicht abgedeckt |
| Deutsches FastText + Levenshtein, lowercase, 50:50 | 0.714 | nicht abgedeckt |
| Übersetzung + englisches FastText + Wort-Matching | 0.746 | 0.688 |
| Übersetzung + englisches FastText/Levenshtein, lowercase, 50:50 | 0.786 | 0.750 |
| Bestehender Vergleich: normalize + String/Übersetzungs-Embedding 50:50 | 0.807 | 0.800 |

Die 33 Fälle enthalten dieselben 28 deutschen und fünf gemischte DE/EN-Szenarien;
die zwei spanischsprachigen Szenarien und drei technischen Leerfälle sind ausgeschlossen.
Die Werte der beiden Spalten sind wegen unterschiedlicher Fallmengen separat zu lesen.
Der Gesamtkatalog enthält auch String-Baselines: Jaro-Winkler mit Lowercasing
erreicht auf den 28 deutschen Fällen beispielsweise F1 0.844. Das macht es noch
nicht zur geeigneten mehrsprachigen Servicepipeline.

Deutsches Word2Vec profitiert hier stark vom Erhalt der Großschreibung.
Die Umstellung auf deutsche Modelle allein liefert keine allgemeine Verbesserung.
Der englische FastText-Hybrid verbessert gegenüber dem aktuellen Service den F1
auf der DE/EN-Menge, liegt aber unter dem bestehenden Übersetzungs-/Sentence-Hybrid.
Alle Aussagen betreffen kleine synthetische Diagnosedaten, keine unabhängige
Testmenge oder durch Tuning gewählte finale Pipeline. Der Service bleibt unverändert.

Precision, Recall, Top-1, Laufzeiten sowie Threshold-, Mutual-Best- und
Hungarian-Ergebnisse stehen in den JSON-Dateien. Die Gesamtdatei speichert auch
Quell-Dateihashes und getrennte Rankings für rein deutsche, alle unterstützten
DE/EN- und ausschließlich gemischte DE/EN-Fälle. Die Rohfeatures und vollständige
Provenienz stehen in den jeweiligen Quelldateien:

- `results/vergleich-wortvektoren.json` (bisheriger Katalog)
- `results/vergleich-deutsche-wortvektoren.json` (deutsches Profil)
- `results/vergleich-englische-hf-wortvektoren.json` (englisches HF-Profil)
- `results/vergleich-deutsches-word2vec-lowercase.json` (nur deutsches Word2Vec,
  Konfiguration wie im deutschen Profil mit `lowercase: true`)

Die neuen vollständigen Profil-Läufe dauerten rund 27 s, 23 s und 13 s inklusive
Modellladen; die FastText-Binärmodelle wurden dabei mit `fasttext==0.9.3` nativ
geladen. Eine erste Gensim-Ausführung wurde wegen hoher Speicherauslastung
abgebrochen und liefert keine Ergebnisdatei. Feature-Caches und Modell-Ladezeiten
verhindern einen direkten Vergleich mit warmen Service-Latenzen.
