# Synonym Matching Louis

Zwei Labelmengen hinein, eine Synonymmatrix mit Original-IDs, Einzelscores und
Combined Score heraus. Der Service verarbeitet extrahierte Labels, kein Graph-XML.

## Zwei Ausführungspfade

- **Service:** `src/main.py` → `synonym_matching.service.match()` → Engine.
- **Forschung:** `research/experiments.json` legt alle Versuche fest, `research/compare.py` führt sie aus. Beide verwenden denselben Matching-Kern.

Der Service importiert keine Forschungsmodule. Docker enthält nur den Service,
Schemas und Vorbereitungsskripte. Forschungsergebnisse verändern den Standard nicht.

## Lokal starten

Alle folgenden Befehle im Ordner `dagu/workflow-services/synonym-matching-louis`:

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
  experiments.json               Baukasten: Preprocessing, Verfahren, Ketten, Mischungen
  experiments.py                 aus experiments.json die Versuche bauen, Sprachprüfung
  compare.py                     Versuche ausführen, Zeiten messen, Ergebnisse speichern
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
  übersetzte Strings, Embeddings und Lexikonadapter. `METHOD_TRAITS` legt fest, was die
  Engine für ein Verfahren vorbereitet (`translate`, `german_only`, `original_text`);
  ein neues Verfahren trägt sich dort ein, die Engine bleibt unverändert.
- `preprocessing.py`: `normalize`, `lowercase`, `split_identifiers`, `lemmatize`,
  `stem`, `remove_stopwords`, `split_compounds`, `expand_abbreviations`,
  `split_label_parts`. Geordnete Liste, `[]` für Rohtexte.
  Zusätzlich darf einmal `translate` (DE→EN, gebündelt) in der Liste stehen, z. B.
  `"preprocessing": ["normalize", "translate", "lowercase"]`: Schritte davor laufen auf
  dem Originaltext, Schritte danach auf dem englischen Text. Das gilt für jedes
  Verfahren (`embedding_preprocessing` entsprechend für Embeddings). Nach `translate`
  wird nicht ein zweites Mal übersetzt; Sprachen außer de/en ergeben einen Fehler.
  Das ist dieselbe Schreibweise wie in den Ketten der Forschung.
- `combinations.py`: Mean, Max, Weighted Mean sowie feste
  Kombinationen und Regeln. `config.combiner` wählt die Kombination. Dazu gehört
  `consensus_fusion`: Übersetzungs- und multilinguales Embedding werden gemittelt, wenn
  sie höchstens `max_gap` (Standard 0.2, fest und nicht getunt) auseinanderliegen,
  sonst gilt der niedrigere Wert.
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

Englisches WordNet und deutsches OdeNet werden beide über `wn` gelesen.
Englisch verwendet fest `omw-en:1.4` (Princeton WordNet 3.0), Deutsch `odenet:1.4`.
Deutsche Labels werden für das englische WordNet weiterhin zuerst übersetzt;
englische Labels und deutsche OdeNet-Eingaben benötigen keine Übersetzung.
Morphy berücksichtigt englische Wortformen; Adjektive einschließlich ihrer
satellites bleiben bei der Suche erhalten. Die Normalisierung für OdeNet nutzt
den wn-Standard; englische Wortformen werden ohne zusätzliche Akzentangleichung
gesucht. Synset-IDs stammen jetzt aus wn statt aus NLTK.

Nach der Umstellung einmal `python scripts/download_lexicons.py --wordnet`
ausführen. Die Daten liegen gemeinsam in `.cache/lexicons/wn`; Matching lädt
keine Ressourcen nach. Ein eigener Pfad unter `config.lexicons.wordnet` verweist
jetzt auf ein wn-Datenverzeichnis mit `wn.db`, nicht auf `nltk_data`.
Vorhandene NLTK-Korpusdateien werden nicht mehr benutzt und nicht automatisch
gelöscht. NLTK bleibt als Bibliothek für Snowball-Stemming erhalten.
Der Docker-Build lädt über das bestehende Vorbereitungsskript ebenfalls die
englischen wn-Daten; ein vorhandenes Image muss dafür neu gebaut werden.

Lemmatisierung braucht spaCy-Modelle, Stemming keinen Korpusdownload.
Kompositazerlegung ist eine einfache DE-Heuristik mit OpenThesaurus-Wortliste.
Stopword Removal kann Negation entfernen. Beide sind bewusst Ablationen.

## Forschung: ein Vergleichslauf

```bash
PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
.venv/bin/python -m research.compare --output results/vergleich.json
```

Ein Befehl führt **alle** in `research/experiments.json` aktivierten Verfahren,
Kombinationen und Preprocessing-Ablationen aus. Optional: `--config` (andere
Konfigurationsdatei) und `--data` (andere Testdaten). Es gibt keine Flags je Verfahren.

**Änderungen an Experimenten (Baukasten):** nur `research/experiments.json` bearbeiten.
Die Datei besteht aus vier Bausteinarten, die zusammengesteckt werden:

- `preprocessing`: benannte Schrittlisten (Preprocessing-Bausteine), z. B.
  `"lemma": ["normalize", "lemmatize", "lowercase"]`.
- `methods`: die verfügbaren Verfahren mit ihren Eigenschaften.
  `"enabled": false` schaltet ein Verfahren samt aller Ketten ab,
  `"languages"` begrenzt die unterstützten Sprachen. Ein Eintrag mit `files` ist ein
  Wortvektormodell (Pfade relativ zum Serviceverzeichnis, Revision und Quelle angeben).
- `chains`: benannte Ketten. Eine Kette ist die Liste der Schritte der Reihe nach,
  das **letzte Glied ist das Verfahren**: `"jw": ["$pre", "jaro_winkler"]`.
  Erlaubt sind Preprocessing-Schritte, `translate` (DE→EN, höchstens einmal) und der
  Platzhalter `$pre`. `$pre` steht für *jede* Pipeline aus `preprocessing`; eine
  Kette mit `$pre` läuft einmal je zulässigem Profil (so entsteht die Ablation).
  Optional begrenzt `methods.<name>.preprocessing_steps` die erlaubten Schritte
  für diesen Platzhalter. In Mischungen gilt die Schnittmenge der variierenden Teile.
  `["normalize", "translate", "levenshtein"]` übersetzt nach `normalize` und rechnet
  Levenshtein auf dem englischen Text; Schritte hinter `translate` gelten für den
  englischen Text. Jede Kette läuft auch allein; ihr Name entsteht automatisch
  (`normalize+stem → levenshtein`). Eine Kette ergibt genau **eine** Matrix.
- `mixes`: Mischungen von Ketten, die über ihren Namen aus `chains` verwendet werden.
  - Gewichtet: `{"weights": {"lev": 1, "multi": 3}}` (25 % / 75 %). Mit `"name"` selbst
    benennen, sonst entsteht der Name aus den Anteilen.
  - Service-Variante: `{"name": "string_multi_50_50", "variant": "weighted_fusion",
    "options": {...}, "parts": ["lev", "jw", "trigram", "multi"]}` mit einer Variante
    aus `src/synonym_matching/combinations.py` (für nichtlineare Regeln wie
    `maximum_fusion`); je Verfahren genau eine Kette.
  - Enthält eine Mischung eine Kette mit `$pre`, läuft sie einmal je Pipeline
    (`lemma/string_multi_50_50`), sonst einmal. `"global_ranking": true` ergänzt die
    Rangheuristik.
- `languages`: erlaubte Sprachen (Standard `["de", "en"]`, wie im Studium gemischt).
  Fälle mit anderen Sprachen (hier die spanischen Fälle 11 und 22) werden nicht
  ausgewertet, aber im Terminal und unter `excluded_cases` im JSON aufgeführt.
  Damit sind zwei der 28 ursprünglichen Falltypen standardmäßig nicht Teil der
  Rankings; `"es"` ergänzen, um sie wieder aufzunehmen.
- Identische Konfigurationen (gleiche Ketten, normierte Gewichte) werden nur einmal
  ausgeführt und unter `skipped_definitions` vermerkt. Mischungen mit deaktivierten
  Verfahren werden ebenfalls übersprungen.
- Fehlende Dateien und nicht unterstützte Sprachen erscheinen als „nicht verfügbar“
  mit Grund, nie als Nullergebnis.

Neue Rechenregeln gehören in `src/synonym_matching/combinations.py`, neue
Similarity-Funktionen zunächst in die Forschung und später in `methods.py`.
`DEFAULT_CONFIG` bleibt unabhängig von `experiments.json`.

### Bedeutungsmerkmale in der Synonymmatrix

Die öffentliche Struktur bleibt `synonymMatrix → matches → scores/combinedScore`.
Über `config.semantic_features` werden Merkmale für ausgewählte Lexikonverfahren
zugeschaltet. Der bisherige Service-Standard und Aufrufe ohne diese Option bleiben
unverändert. Beispiel:

```json
{
  "methods": ["levenshtein", "wordnet"],
  "semantic_features": {
    "wordnet": ["reference_synset_count", "student_synset_count", "antonym", "wup_similarity"]
  },
  "combiner": {"kind": "mean", "methods": ["levenshtein"]}
}
```

In `scores` stehen dann neben den bisherigen Methodenscores beispielsweise
`wordnet_reference_known`, `wordnet_student_known`, `wordnet_pair_known`,
`wordnet_shared_synset`, `wordnet_antonym` und `wordnet_wup_similarity`.
Die übrigen Merkmale werden genauso mit `wordnet_` bzw. `odenet_` vorangestellt.
Bei Path/Wu-Palmer wird `taxonomy_available` automatisch mit ausgegeben.
`reference` bezeichnet die Musterlösung, `student` die Schülerlösung.

Die drei Abdeckungsmerkmale werden immer ergänzt: Ein Relationswert 0 bei
`pair_known=0` hat eine andere Grundlage als 0 bei zwei gefundenen Labels.
Auch vollständige Labelabdeckung garantiert keine vollständigen Beziehungen oder
die richtige Lesart. WordNet-Abdeckung bezieht sich auf die englischen Suchtexte
nach Übersetzung. `shared_synset` ist ein lesbarer Alias des bisherigen
WordNet-/OdeNet-Scores; der alte Methodenname bleibt erhalten.

`"openthesaurus": []` aktiviert Abdeckung und `openthesaurus_shared_group`, ohne
erfundene Taxonomierelationen. `"wn_translation": []` ergänzt zusätzlich
`reference_linked` und `student_linked`: Ein Lexikoneintrag kann vorhanden sein,
ohne eine englische Verknüpfung zu besitzen. Die Quellen müssen jeweils unter
`methods` ausgewählt sein. Eine leere Liste bedeutet hier nur Abdeckungsmerkmale.

Zusatzmerkmale werden nicht automatisch gemittelt oder abgeschnitten.
Lesartenanzahlen bleiben echte Zählwerte und können größer als 1 sein;
das Ausgabeschema erlaubt dies gezielt für die beiden Synsetanzahlen je Quelle.
Die übrigen Scores behalten ihren bisherigen Wertebereich, `combinedScore` bleibt
in [0,1]. Die bereits getestete Regel ist auch im Service explizit auswählbar:

```json
{"kind": "evidence", "baseline": "translated_embedding", "lexicon": "wordnet"}
```

Sie verwendet dieselbe Funktion und dieselben ungerundeten Bedeutungsmerkmale wie
der Forschungslauf. Ohne explizite Merkmalsliste werden ihre sechs notwendigen
Merkmale automatisch angefordert; eine explizite Liste muss diese enthalten.
Das ist weiterhin eine vorläufige Heuristik, kein nachgewiesener Qualitätssprung.
Es wird kein Feld `equivalent` oder `not_equivalent` ergänzt. Threshold und weitere
Zuordnung bleiben nachgelagert; gerundet wird erst für die JSON-Ausgabe.

Ein vollständiges Eingabebeispiel mit dieser Regel und unfiltrierten Kandidaten:

```bash
PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
.venv/bin/python src/main.py --input examples/semantic-features-input.json
```

### Konservative Evidenzfusion (Forschungsversuch)

Ein neuer Versuch `translated_embedding_wordnet_evidence` verwendet das übersetzte
monolinguale Embedding als Basis und die bestehende englische WordNet-Kette als
Evidenz. Es werden keine neuen Gewichte gesucht. Die Regel ist fest:

- Beide Labels müssen gefunden sein und jeweils genau einen erfassten Synset haben.
- Gemeinsamer Synset ohne Gegenrelation: Score 1.
- Kein gemeinsamer Synset, aber explizite Antonym- oder Ober-/Unterbegriffsrelation: Score 0.
- Sonst bleibt der auf [0,1] begrenzte Basisscore unverändert, auch bei widersprüchlicher Evidenz.

Eine einzige erfasste Lesart ist keine garantierte Eindeutigkeit in der Aufgabe.
Die Endpunkte 0 und 1 sind heuristische Regelentscheidungen, keine Wahrscheinlichkeiten.
Die Ablehnung hierarchischer Beziehungen setzt die strenge Labelgleichwertigkeit
unserer Annotationen voraus. Path und Wu-Palmer werden nicht zur Synonymbestätigung
benutzt. Diese Forschungskombination verändert den Service-Standard nicht.

Im Baukasten: `{"name": "...", "evidence": true, "parts": ["trans_emb", "wordnet"]}`.
Der erste Teil ist die Basis, der zweite WordNet oder OdeNet mit den sechs
Abdeckungs-/Lesarten-/Relationsmerkmalen. Einzelne Änderungen stehen mit IDs,
Vorher-/Nachher-Score und Grund unter `records[].evidence_changes`.
Die Rechenzeit dieser Kombination enthält zusätzlich die angeforderte Relationsdiagnose.

Nur den neuen Versuch auf Laborverwaltung ausführen:

```bash
PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
.venv/bin/python -m research.compare --data research/laboratory-cases.json \
  --only translated_embedding_wordnet_evidence --output results/evidence-fusion.json.gz
```

`--only` wählt vorhandene Experiment-IDs aus. Ohne diese Option läuft weiterhin
der vollständige JSON-Baukasten. Konfiguration und Auswahl werden gespeichert.

### Kleine Probe: Abkürzungen und Labelbestandteile

Zwei optionale deutsche Schritte, ohne neue Modelle:

- `expand_abbreviations`: `Nr.`/`Nr` am Wortende wird zu `Nummer`, auch in `GebäudeNr.`.
- `split_label_parts`: kombiniert diese Auflösung mit `split_identifiers` und der
  vorhandenen OpenThesaurus-Kompositazerlegung. Zusätzlich gilt ein linker Teil auf
  `e` als bekannt, wenn die Form ohne `e` im Lexikon steht: `Geräteraum` → `geräte raum`.

Andere Sprachen bleiben unverändert. Die Pluralheuristik ist bewusst einfach und
kann falsch zerlegen; sie ist keine Lemmatisierung. Ohne vorhandenes OpenThesaurus
ist die Kompositazerlegung nicht verfügbar. Das bisherige `split_compounds`, die
Standardpipeline und das Outputschema bleiben unverändert.

Gezielter Vergleich mit derselben Übersetzungs-/Embedding-Baseline:

```bash
PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
.venv/bin/python -m research.compare --data research/laboratory-cases.json \
  --only 'normalize → translated_embedding' \
  'normalize+expand_abbreviations → translated_embedding' \
  'normalize+split_label_parts → translated_embedding' \
  --output results/label-parts-laboratory.json.gz
```

Für die kleine Objekt-/Nummernprobe denselben Aufruf mit
`--data research/label-parts-cases.json` und einem anderen Ausgabepfad verwenden.
Ausgabedateien werden nicht überschrieben. Die zwei neuen festen Ketten stehen in
`research/experiments.json`; es entsteht kein zusätzliches Kreuzprodukt von Varianten.

Ergebnis vom 13.11.2026, Seed 42, Threshold 0,5: fünf Laborvarianten, **nur geänderte
Schülerlabels**, jeweils gegen alle Referenzkandidaten. Die folgenden Werte bewerten
Threshold-Treffer, keine 1:1-Zuordnung. Rohdaten einschließlich Konfiguration und
Modellrevisionen: `results/label-parts-laboratory-20261113.json.gz` (lokal, ignoriert).

| Vorverarbeitung vor Übersetzung + monolingualem Embedding | Precision | Recall | F1 | FP |
| --- | ---: | ---: | ---: | ---: |
| normalize (Baseline) | 0,611 | 0,818 | 0,699 | 100 |
| + expand_abbreviations | 0,348 | 0,880 | 0,499 | 317 |
| + split_label_parts (enthält Abkürzungsauflösung) | 0,290 | 0,792 | 0,424 | 373 |

Auf der kleinen Entwicklungsprobe mit 24 Paaren steigt F1 dagegen von 0,533 auf
0,625 (nur Abkürzungen) bzw. 0,588 (Labelzerlegung); alle fünf positiven Paare
werden erkannt statt vier. Das verallgemeinert nicht auf die Laborvarianten.
Rohdaten: `results/label-parts-targeted-20261113.json.gz`.

| Gezieltes Paar | Baseline | Abkürzungen | Labelzerlegung |
| --- | ---: | ---: | ---: |
| Gebäude / GebäudeNr. (negativ) | 0,5158 | 0,5662 | 0,5662 |
| GebäudeNr. / Gebäudenummer (positiv) | 0,6136 | 1,0000 | 1,0000 |
| Geräte / Geräteraum (negativ) | 0,7260 | 0,7260 | 0,7260 |
| GeräteNr. / Gerätenummer (positiv) | 0,2584 | 0,5713 | 1,0000 |

Fazit dieser Entwicklungsprobe: bessere Erkennung einzelner Schreibvarianten,
aber **keine Reduktion falscher Treffer bei unverändertem Threshold**. Gemeinsame
Bestandteile erhöhen auch bei fachlich verschiedenen Labels die Ähnlichkeit.
Die Schritte bleiben optional; aus diesen Ergebnissen folgt keine Änderung des
Service-Standards und keine Aussage über einen separat validierten Threshold.

### Optionale Konfliktregel für Labelbestandteile

`label_part_compatibility` analysiert normalisierte **Originaltexte** unabhängig vom
Preprocessing der Embeddings. Die kleine feste DE/EN-Liste erkennt Nummern und
Räume sowie Gebäude, Geräte, Etagen, Räume und Projekte als Objektbestandteile.
Abkürzungen und bekannte Endungen werden ohne Modell oder Lexikon zerlegt.
Der vollständige Umfang der Liste steht direkt in `methods.py`.

Der Wert ist 0 bei einem erkannten Konflikt, sonst neutral 1:

- Nur ein Label enthält `Nummer`/`number`/`ID`: möglicher Objekt-/Attributkonflikt.
- Beide sind Nummern, aber ihre bekannten Objektbestandteile widersprechen sich.
- Ein Label bezeichnet einen Raum, das andere dasselbe erkannte Objekt ohne Raumzusatz.

Unbekannte Objektbestandteile werden nicht als unterschiedliche Objekte gewertet.
Eine erkannte Nummer kann trotzdem einen Abschlag auslösen, wenn beim anderen Label
kein Nummernmarker erkannt wird. Implizite Kennungen, andere Sprachen, Mehrdeutigkeit
(etwa englisches `number`) und unbekannte Abkürzungen sind Grenzen dieser Heuristik.
Neutral 1 bedeutet ausdrücklich **keine Synonymbestätigung**. Leere Labels bleiben
wie bisher nicht zuordenbar. Das zusätzliche numerische Merkmal steht unter `scores`;
das Outputschema und der Service-Standard ändern sich nicht.

Die Variante `label_part_fusion` verwendet:
`combinedScore = clip(translated_embedding, 0, 1) * (1 - penalty * (1 - compatibility))`.
Für den Versuch ist `penalty = 0.5` festgelegt, ohne Parameteroptimierung.
Konflikte halbieren den Basisscore, alle übrigen Scores bleiben unverändert.
Ein Basisscore von 1 bleibt damit bei Threshold 0,5 trotz Konflikt ein Treffer.

Service-Konfiguration für die optionale Variante:

```json
{
  "methods": ["translated_embedding", "label_part_compatibility"],
  "preprocessing": ["normalize"],
  "embedding_preprocessing": ["normalize"],
  "combiner": {
    "kind": "variant",
    "name": "label_part_fusion",
    "options": {"penalty": 0.5}
  }
}
```

Im JSON-Baukasten stehen die zwei festen Mischungen
`translated_embedding_part_conflicts` (ursprüngliche Baseline + Konfliktregel) und
`translated_embedding_parts_and_conflicts` (zusätzlich zerlegte Embedding-Eingabe).
Die Regel wird nicht als normaler Similarity-Score mitgemittelt.

```bash
PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
.venv/bin/python -m research.compare --data research/laboratory-cases.json \
  --only 'normalize → translated_embedding' \
  'normalize+split_label_parts → translated_embedding' \
  translated_embedding_part_conflicts translated_embedding_parts_and_conflicts \
  --output results/label-conflicts-laboratory.json.gz
```

Entwicklungsvergleich vom 13.11.2026, Seed 42, Threshold 0,5, geänderte Schülerlabels
gegen alle Referenzkandidaten der fünf Laborvarianten:

| Variante | TP | FP | FN | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Ursprüngliche Übersetzungs-/Embedding-Baseline | 157 | 100 | 35 | 0,611 | 0,818 | 0,699 |
| Baseline + Konfliktregel | 157 | 12 | 35 | 0,929 | 0,818 | 0,870 |
| Zerlegte Embedding-Eingabe | 152 | 373 | 40 | 0,290 | 0,792 | 0,424 |
| Zerlegte Eingabe + Konfliktregel | 152 | 158 | 40 | 0,490 | 0,792 | 0,606 |

Die Regel entfernt hier 88 falsche Treffer, ohne einen der 157 richtigen zu verlieren.
Auf allen Laborpaaren sinkt FP von 419 auf 103 bei unveränderten TP/FN (579/35).
`Gebäude / GebäudeNr.` fällt von 0,5158 auf 0,2579, `Geräte / Geräteraum` von 0,7260
auf 0,3630. `GebäudeNr. / Gebäudenummer` bleibt mit 0,6136 ein Treffer.
Ein vorher übersehenes Synonym wird durch einen reinen Abschlag nicht neu erkannt.

Die kleine Objekt-/Nummernprobe verbessert sich von F1 0,533 (FP 6, FN 1) auf 0,889
(FP 0, FN 1); mit zusätzlicher Zerlegung erreicht sie dort 1,0. Auf den 33 auswertbaren
bestehenden synthetischen Kontrollszenarien steigt F1 von 0,680 auf 0,723, FP sinkt
von 23 auf 17 bei unveränderten TP/FN (34/9). Das sind ebenfalls bekannte
Entwicklungsdaten, kein unabhängiger Nachweis für neue Aufgaben.

Alle drei Läufe sind lokal reproduzierbar gespeichert, jeweils mit Rohscores,
Konfiguration und Modellrevisionen (im ignorierten Ordner `results`):
`label-conflicts-laboratory-20261113.json.gz`, `label-conflicts-targeted-20261113.json.gz`
und `label-conflicts-control-20261113.json.gz`. Für die anderen Datensätze den Aufruf
mit `--data research/label-parts-cases.json` beziehungsweise `research/model-cases.json`
und eigenem Ausgabepfad verwenden. Nächste notwendige Prüfung: unabhängige Aufgaben
mit echten Synonymen für Kennungen und bisher unbekannten Objektbezeichnungen.

### Vollständige semantische Fusion und Ablationen (19.11.2026)

Die optionale Kombination `{"kind": "semantic"}` verwendet die vorhandenen Methoden
`levenshtein`, `jaro_winkler`, `char_trigram`, `translated_embedding`, `wordnet` und
`label_part_compatibility`. Sie aktiviert die neun benötigten WordNet-Merkmale auch
im Service automatisch. Alle Einzelscores bleiben unter `scores` sichtbar; der
Service-Standard und das Outputschema bleiben unverändert.

Feste experimentelle Regel, **keine Kalibrierung oder Parameteroptimierung**:

1. Basis: 75 % übersetztes Embedding + 25 % Mittel der drei Stringverfahren.
2. Lexikonevidenz gilt nur bei beidseitiger Abdeckung und genau einer erfassten
   Lesart pro Seite. Unbekannt bedeutet keine Gegenevidenz.
3. Gemeinsamer Synset ohne Gegenrelation: Mindestscore 0,9. Bei verfügbarer
   Taxonomie steigt dieser um `0,1 * q`, mit `q = (Path + Wu-Palmer) / 2`.
4. Explizite Gegenrelation ohne gemeinsamen Synset: Abschlag 50 %, bei verfügbarer
   Taxonomie zusätzlich `25 % * (1 - q)`. Ontologische Nähe bestätigt allein nichts.
5. Anschließend halbiert ein erkannter Nummern-/Raumkonflikt den Score wie bisher.

Die Parameter stehen zentral in `SEMANTIC_POLICY` und werden im Forschungsergebnis
unter `semantic_fusion_policy` gespeichert. `disabled` schaltet einzelne Gruppen
ab: `strings`, `coverage`, `ambiguity`, `synsets`, `relations`, `ontology`, `conflicts`.
Alle Merkmale werden trotzdem einmal berechnet und zwischen Ablationen geteilt.

Ein Aufruf für Baseline, Konfliktregel, vollständige Fusion und sieben Ablationen:

```bash
PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
.venv/bin/python -m research.compare --data research/laboratory-cases.json \
  --only 'normalize → translated_embedding' translated_embedding_part_conflicts \
  semantic_full semantic_without_strings semantic_without_coverage \
  semantic_without_ambiguity semantic_without_synsets semantic_without_relations \
  semantic_without_ontology semantic_without_conflicts \
  --output results/semantic-fusion-laboratory.json.gz
```

Für die Kontrollfälle `--data research/model-cases.json` und einen anderen Ausgabepfad
verwenden. Die JSON-Datei enthält Rohscores, Daten, Modelle, Seed und Konfiguration.
Eine Wiederholung mit gleicher Ausgabedatei wird wie bisher nicht überschrieben.

**Ergebnis: geänderte Schülerlabels der fünf Laborvarianten**, Threshold 0,5, Seed 42:

| Versuch | TP | FP | FN | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline | 157 | 100 | 35 | 0,611 | 0,818 | 0,699 |
| Bisherige Konfliktregel | 157 | 12 | 35 | 0,929 | 0,818 | 0,870 |
| Vollständige Fusion | 155 | 7 | 37 | 0,957 | 0,807 | 0,876 |
| Ohne Stringanteil | 157 | 12 | 35 | 0,929 | 0,818 | 0,870 |
| Ohne Abdeckungsmaske | 155 | 7 | 37 | 0,957 | 0,807 | 0,876 |
| Ohne Mehrdeutigkeitsprüfung | 152 | 8 | 40 | 0,950 | 0,792 | 0,864 |
| Ohne Synset-Anhebung | 155 | 7 | 37 | 0,957 | 0,807 | 0,876 |
| Ohne Relationsabschlag | 155 | 7 | 37 | 0,957 | 0,807 | 0,876 |
| Ohne Ontologie-Modulation | 155 | 7 | 37 | 0,957 | 0,807 | 0,876 |
| Ohne Labelkonflikte | 155 | 56 | 37 | 0,735 | 0,807 | 0,769 |

Der zusätzliche Stringanteil entfernt gegenüber der Konfliktregel fünf falsche
Treffer, verliert aber `Wissen\\nschaftler / Forschende` und `Anzahl / Quantity`.
Synset-Anhebung und Ontologie verändern jeweils einen Score, aber keine Entscheidung
bei 0,5; der Relationsabschlag greift hier bei keiner eindeutigen Lesartenkombination.
Die Abdeckungsmaske ist in dieser Regel redundant zur Bedingung genau einer Lesart.
Das bedeutet nicht, dass unbekannte Einträge allgemein ignoriert werden dürfen.

Auf den 33 auswertbaren bekannten Kontrollszenarien: Baseline F1 0,680 (TP/FP/FN
34/23/9), Konfliktregel 0,723 (34/17/9), volle Fusion 0,742 (33/13/10). Ohne
Mehrdeutigkeitsprüfung steigt dort F1 auf 0,786, während dieselbe Ablation im Labor
schadet. Es liegt kein aufgabenübergreifend bestätigter Vorteil vor.

**Bewertung:** Mehr Kennzahlen ergeben noch keine bessere Pipeline unter der
Vorgabe, richtige Treffer zu erhalten. Die bisherige Konfliktregel bleibt für dieses
Ziel die vorsichtigere Forschungsreferenz. Keine automatische Umstellung des Services.
Alle Daten sind bekannte Entwicklungsdaten; insbesondere die Konfliktregeln wurden
aus Laborfehlern abgeleitet. Unabhängige Aufgaben und Threshold-Validierung fehlen.

Lokale Ergebnisse im ignorierten Ordner `results`:
`semantic-fusion-laboratory-final-20261119.json.gz`,
`semantic-fusion-control-20261119.json.gz` und
`semantic-fusion-summary-20261119.json` (Metriken, Ablationsbeiträge, entfernte falsche
und verlorene richtige Treffer, konkrete Labelpaare und Hashes der Rohdateien).

### Komponentenweise Bewertung: erster Mittelwert-Versuch (Vergleichsbaseline, 19.11.2026)

Optionales Verfahren `component_matching`, auswählbar in Service und JSON-Baukasten.
Es verwendet keine neuen Modelle und verändert den Standard nicht:

1. Eine Zerlegungsebene mit `split_label_parts` (DE) beziehungsweise Identifier-/
   Worttrennung (EN); ausdrücklich angegebene Sprache `de`/`en` erforderlich.
2. Alle eindeutigen Bestandteile pro Sprache werden gebündelt verglichen: dieselben
   String-, Embedding-, Abdeckungs-, Synset-, Lesarten-, Relations- und Taxonomiemerkmale.
3. Komponentenpaar-Score mit der zuletzt getesteten semantischen Fusion, aber
   **ohne Nummern-/Raumabschlag**. Deren feste Gewichte werden unverändert übernommen,
   um zunächst die Wirkung der Zerlegung zu prüfen; sie sind weiterhin nicht kalibriert.
4. Optimale 1:1-Paarung der Komponenten anhand dieser Scores (Hungarian).
5. Summe der gewählten Scores geteilt durch die größere Komponentenanzahl.
   Fehlende Partner zählen als 0, wiederholte Bestandteile werden nicht entfernt.

Der neue Score steht unter `scores.component_matching` und kann allein den
`combinedScore` bilden. Die einzelnen Merkmale erscheinen zusätzlich als
`component_matching_...`: jeweils über **dieselbe ausgewählte Paarung** gemittelt,
einschließlich Nullen für fehlende Partner. Es wird nicht jedes Merkmal separat optimal
zugeordnet. Abdeckungs-/Relationswerte sind dadurch Anteile, keine neuen Ja/Nein-Urteile.
Synsetanzahlen bleiben im Forschungstrace; öffentlich werden stattdessen die Anteile
mehrdeutiger Bestandteile (`..._reference_ambiguous`, `..._student_ambiguous`) ausgegeben.
So bleibt das bestehende Outputschema unverändert.

Service: `{"methods": ["component_matching"], "preprocessing": ["normalize"]}`.
Die Methode liest die Originaltexte; Vorverarbeitung der Teilvergleiche ist im
Backend festgelegt. Bestehende Modelle und deren Cache werden für alle Labelpaare
wiederverwendet. In der Forschungsdatei stehen Zerlegungen, Komponentenrohmatrizen,
Konfiguration und gewählte Paarungen unter `features[].component_evidence`.

```bash
PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
.venv/bin/python -m research.compare --data research/laboratory-cases.json \
  --only 'normalize → translated_embedding' translated_embedding_part_conflicts \
  semantic_full semantic_without_conflicts 'normalize → component_matching' \
  --output results/components-laboratory.json.gz
```

Für `research/label-parts-cases.json` und `research/model-cases.json` denselben Aufruf
mit eigenem Ausgabepfad verwenden. Alle Baselines bleiben auswählbar.

**Geänderte Laborlabels**, Seed 42, Threshold 0,5, bekannte Entwicklungsdaten:

| Verfahren | TP | FP | FN | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Übersetzungs-/Embedding-Baseline | 157 | 100 | 35 | 0,611 | 0,818 | 0,699 |
| Bisherige Konfliktregel | 157 | 12 | 35 | 0,929 | 0,818 | 0,870 |
| Vollständige Fusion | 155 | 7 | 37 | 0,957 | 0,807 | 0,876 |
| Dieselbe Komponentenpaar-Fusion auf unzerlegten Labels (ohne Konflikte) | 155 | 56 | 37 | 0,735 | 0,807 | 0,769 |
| Komponentenmatching mit Mittelwert | 128 | 606 | 64 | 0,174 | 0,667 | 0,277 |

Gegenüber der Embedding-Baseline: 62 falsche Treffer entfernt, aber 568 neue;
37 richtige verloren und acht neue erkannt. Beispiel für das verbleibende Problem:
`GeräteNr. / Raumnummer`: Teilscore Geräte/raum 0,2671, Nummer/nummer 0,9435,
Mittelwert 0,6053. Ein gemeinsamer Zusatz überdeckt damit weiterhin einen schwachen
Objektvergleich. Bei 552 der 606 falschen Treffer ist ein Nummernpaar zugeordnet.

Die gezielte 24-Paar-Probe erkennt alle fünf Positiven (Baseline vier), erzeugt aber
sieben statt sechs falsche Treffer (F1 0,588 statt 0,533). Auf 33 bestehenden
Kontrollszenarien: TP/FP/FN 32/18/11, F1 0,688; die Konfliktregel erreicht dort 0,723.
Ein perfekter Teiltreffer bei einem fehlenden Bestandteil ergibt genau 0,5 und wird
bei Threshold 0,5 noch akzeptiert; Rundung kann zusätzlich Grenzwerte verdecken.

**Keine Verbesserung durch diese konkrete Mittelwertvariante.** Weder Standardpipeline
noch Threshold wurden an das Ergebnis angepasst. Eine andere Aggregation oder eine
Unterscheidung von Objekt und Attribut ist ein späteres, gesondertes Experiment.
Die Ergebnisse erlauben keine pauschale Aussage gegen Komponentenmatching.

Lokal gespeichert: `results/components-laboratory-20261119.json.gz`,
`results/components-targeted-20261119.json.gz`, `results/components-control-20261119.json.gz`
und `results/components-summary-20261119.json`. Die gespeicherten Komponenten- und
Gesamtlabel-Scores wurden nachgerechnet und die öffentlichen Matrixausgaben gegen das
unveränderte Schema geprüft. `components.py` enthält die neue Berechnung; der
Service und der Forschungslauf nutzen dasselbe Backend.

### Komponentenmerkmale vor der Fusion (korrigierte Variante, 19.11.2026)

`component_feature_fusion` bildet **keinen fusionierten Score je Bestandteil** mehr.
String- und Embedding-Werte werden zunächst separat auf Gesamtlabel-Ebene gemittelt;
erst danach wird einmal die unveränderte `semantic_fusion` angewandt. Ihre Gewichte,
Lesartenprüfung und bisherige Nummern-/Raumkonfliktregel bleiben ausdrücklich erhalten.
`component_matching` bleibt als bisheriger, vorzeitig fusionierender Vergleich erhalten.

Die neue Variante erkennt gezielt Endungen/Abkürzungen für Nummer und Raum (DE/EN).
`GebäudeNr.` wird Gebäude + Nummer, `Geräteraum` Geräte + Raum; normale Labels wie
`Kunde registrieren`, `Order Item` und `Vorname` bleiben unzerlegt. Mehrwortige
Objektbezeichnungen vor einem erkannten Zusatz werden als ein Objektteil erhalten.
Unbekannte Präfixe werden nicht geraten oder verworfen. Es ist keine allgemeine
Kompositazerlegung oder grammatische Analyse.

| Merkmal | Zusammenführung nach gemeinsamer Komponentenpaarung |
| --- | --- |
| Levenshtein/Jaro-Winkler/Trigramme | Jeweils Mittel, fehlender Partner zählt 0 |
| Embedding | Separater Mittelwert, fehlender Partner zählt 0 |
| Gemeinsamer Synset | Nur 1, wenn alle Bestandteile vollständig synonym zugeordnet sind |
| Abdeckung | Pro Seite alle Bestandteile bekannt; `pair_known` erfordert beide Seiten |
| Mehrdeutigkeit | Maximum der Komponenten-Synsetanzahlen; öffentlich nur Mehrdeutigkeitsflag |
| Hypernym/Hyponym/Antonym | Objektbeziehung nur bei vollständiger Paarung und synonymem Zusatz |
| Path/Wu-Palmer | Objektwert nur bei synonymem Zusatz und verfügbarer Taxonomie |

Zur Paarung dienen nur String-/Embedding-Werte, keine vorherige Bedeutungsfusion.
Objekt wird mit Objekt und Zusatz mit Zusatz gepaart. Das verhindert beispielsweise,
dass das gemeinsame Nummer den fehlenden Objektpartner ersetzt. Die Rollen stammen
ausschließlich aus der erkannten Struktur, nicht aus einem neuen Sprachmodell.

Service-Konfiguration: `{"methods": ["component_feature_fusion"], "preprocessing": ["normalize"]}`.
Im Forschungslauf ist die ID `normalize → component_feature_fusion`. Im Trace stehen
`alignmentScores`, `whole_label_scores` und `whole_label_semantic_features`; daraus
lässt sich die einzige abschließende Fusion exakt nachrechnen. Das Outputschema bleibt
unverändert; neue Werte stehen unter `scores.component_feature_fusion_...`.

```bash
PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
.venv/bin/python -m research.compare --data research/laboratory-cases.json \
  --only 'normalize → translated_embedding' translated_embedding_part_conflicts \
  semantic_full 'normalize → component_matching' 'normalize → component_feature_fusion' \
  --output results/component-features-laboratory.json.gz
```

Ergebnis auf **geänderten Laborlabels**, Seed 42, Threshold 0,5:

| Variante | TP | FP | FN | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Embedding-Baseline | 157 | 100 | 35 | 0,611 | 0,818 | 0,699 |
| Konfliktregel | 157 | 12 | 35 | 0,929 | 0,818 | 0,870 |
| Vollständige Fusion | 155 | 7 | 37 | 0,957 | 0,807 | 0,876 |
| Früherer Komponentenmittelwert | 128 | 606 | 64 | 0,174 | 0,667 | 0,277 |
| Erst Merkmale zusammenführen, dann Fusion | 167 | 480 | 25 | 0,258 | 0,870 | 0,398 |

Gegenüber der Embedding-Baseline werden 96 falsche Treffer entfernt und zwölf neue
richtige erkannt; es entstehen aber 476 neue falsche, und zwei richtige gehen verloren.
In der gezielten 24-Paar-Probe werden dagegen alle fünf Positiven ohne FP erkannt.
Beispiele: Gebäude/GebäudeNr. 0,2500, GebäudeNr./Gebäudenummer 0,9479,
Geräte/Geräteraum 0,2359, GeräteNr./Gerätenummer 0,9435.

Ein gemeinsames Nummer kann weiterhin die gemittelten String-/Embedding-Werte
anheben, auch wenn der zusammengeführte Synsetwert korrekt 0 ist. Die unveränderte
Fusion wertet fehlende Synonym-Evidenz nicht automatisch negativ. Bei unbekannten
Objektbestandteilen greifen weder Lexikonkorrektur noch zwingend die alte Konfliktregel.
Beispiel EtagenNr./GebaeudeNr.: Abdeckung unvollständig, Synset 0, Score dennoch 0,6078.

Auf 33 bekannten Kontrollszenarien erreicht die neue Variante F1 0,695 (TP/FP/FN
33/19/10), die vollständige Fusion 0,742 und die Konfliktregel 0,723. Der geänderte
Ablauf allein ist damit keine allgemeine Qualitätsverbesserung. Keine Parameter oder
Thresholds nachträglich angepasst; Standardpipeline nicht umgestellt. Alle Daten sind
bekannte Entwicklungsdaten, keine unabhängige Validierung.

Lokal gespeichert: `results/component-features-laboratory-20261119.json.gz`,
`results/component-features-targeted-20261119.json.gz`,
`results/component-features-control-20261119.json.gz` sowie
`results/component-features-summary-20261119.json`. Separate Merkmalsmittelwerte,
abschließende Fusion und öffentliche Schemakompatibilität wurden nachgeprüft.

### Rollenfreie Komponenten: gewichtete Basis und Evidenzregeln

Neue optionale Methode `component_evidence`. Sie verwendet weder Objekt-/Attributrollen
noch die alte Konfliktregel. Alle zugeordneten Bestandteile zählen gleich viel.
Die früheren Rollen- und Konfliktvarianten bleiben ausschließlich als Vergleiche erhalten.

- Sichtbare Abkürzungen, camelCase und Unterstriche erlauben Zerlegung.
- Unbekannte deutsche Einzelwörter werden mit der vorhandenen Kompositazerlegung
  untersucht; bekannte Ganzwörter wie Vorname bleiben erhalten.
- Normale Mehrwortlabels bleiben atomar. Gibt eine Phrase eine anderweitig erkannte
  Zerlegung exakt wieder (Gebäude Nummer vs. GebäudeNr.), wird dieselbe Teilung genutzt.
- Alle eindeutigen Komponenten werden gebündelt mit vorhandenen String-, Embedding-
  und WordNet-Verfahren verglichen. Optimale 1:1-Paarung anhand String/Embedding,
  keine Rollenbeschränkung. Fehlende Partner zählen 0; keine Rekursion.

Stringmetriken und Embedding werden getrennt gemittelt. `shared_synset_fraction`
ist der Anteil synonym belegter Paare, `shared_synset` dagegen 1 nur bei vollständiger
Paarung und Synsetübereinstimmung aller Bestandteile. `lexicon_coverage` ist der Anteil
beidseitig bekannter Paare; Seitenabdeckung und Mehrdeutigkeitsanteile bleiben separat.
Relationswerte sind Anteile über mögliche Lesarten, noch keine Gegenbeweise. Ontologische
Nähe wird mit eigener Taxonomieabdeckung gespeichert, aber nicht als Synonymbonus benutzt.

Die Fusion berechnet mit konfigurierbaren Gewichten:

```text
B = string_weight * String + (1 - string_weight) * Embedding
L = shared_synset_fraction + (1 - lexicon_coverage) * B
Score = (1 - lexicon_weight) * B + lexicon_weight * L
```

Unbekannte Lexikonanteile erhalten damit neutral B, nicht 0. Bekannte Teilübereinstimmung
kann trotzdem erhöhen; sie bestätigt keine Gesamtgleichwertigkeit. Bei vollständig
bekanntem Beispiel mit String 0,6, Embedding 0,675 und Synsetanteil 0,5 ergibt
die aktuelle Gewichtung (25 % String, 75 % Embedding, 30 % Lexikonevidenz) 0,609375.
Die Gewichte sind vorab gewählte Versuchsparameter,
keine gelernten oder validierten Wahrscheinlichkeiten.

Mit `rules: true` gelten anschließend folgende Regeln:

- Vollständige, beidseits jeweils einsinnig erfasste Synonym-Evidenz ohne Gegenrelation:
  mindestens `synonym_floor`.
- Antonym-Evidenz bei einem zugeordneten Paar: höchstens `relation_cap`, wenn beide
  Einträge genau eine Lesart haben und keinen gemeinsamen Synset.
- Hierarchie-Evidenz: dieselbe Begrenzung nur bei vollständiger Paarung und synonymem
  Rest. Gemeint ist strikte Gleichwertigkeit, keine zulässige Verallgemeinerung.
- Gegenevidenz hat Vorrang. Eine erfasste Lesart garantiert jedoch keine passende
  Bedeutung in der Aufgabe; besonders mehrdeutige Wörter führen oft zu keiner Regel.

Service-Konfiguration (Outputschema unverändert):

```json
{
  "methods": ["component_evidence"],
  "combiner": {
    "kind": "component_evidence",
    "options": {
      "string_weight": 0.25,
      "lexicon_weight": 0.3,
      "rules": true,
      "synonym_floor": 0.9,
      "relation_cap": 0.0
    }
  }
}
```

Ohne den speziellen Combiner liefert die Methode nur die 50:50-String-/Embedding-Basis.
Im Baukasten teilen `component_evidence_weighted` und `component_evidence_rules`
dieselbe Merkmalskette und unterscheiden sich nur durch den Regelschalter. Parameter
stehen unter `mixes[].options` und werden vollständig im Ergebnis gespeichert.

```bash
PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
.venv/bin/python -m research.compare --data research/laboratory-cases.json \
  --only 'normalize → translated_embedding' translated_embedding_part_conflicts \
  'normalize → component_evidence' component_evidence_weighted component_evidence_rules \
  --output results/component-evidence-laboratory.json.gz
```

Historischer Lauf mit 50 % String und 50 % Embedding (vor der Umstellung auf 25:75):
bekannte Entwicklungsdaten, geänderte Laborlabels, Seed 42, Threshold 0,5.
Die folgende Tabelle bezieht sich weiterhin auf den historischen 50:50-Lauf:

| Variante | TP | FP | FN | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Embedding-Baseline | 157 | 100 | 35 | 0,611 | 0,818 | 0,699 |
| Alte Konfliktregel | 157 | 12 | 35 | 0,929 | 0,818 | 0,870 |
| Rollenfreie String-/Embedding-Basis | 105 | 488 | 87 | 0,177 | 0,547 | 0,268 |
| Gewichtete Lexikonevidenz | 104 | 488 | 88 | 0,176 | 0,542 | 0,265 |
| Zusätzlich Evidenzregeln | 104 | 488 | 88 | 0,176 | 0,542 | 0,265 |

Auf der kleinen 24-Paar-Probe: Basis TP/FP/FN 5/5/0, mit Lexikonevidenz und Regeln
5/10/0. Auf 33 bekannten Kontrollszenarien: Basis F1 0,759 (33/11/10), gewichtete
Evidenz mit/ohne Regeln 0,721 (31/12/12); alte Konfliktregel 0,723 (34/17/9).
Die Regeln ändern je einen Score im vollständigen Labor- und Kontrolllauf, aber keine
Threshold-Entscheidung. Fehlende eindeutige Lexikonevidenz begrenzt ihre Anwendbarkeit.

Die Startgewichtung verbessert damit nicht beide Datensätze. Teilübereinstimmungen
können weiterhin hohe Werte erzeugen, bekannte Lexikoneinträge können zur falschen
Bedeutung gehören, und atomare Paraphrasen passen nicht immer zu einer Zerlegung.
Außerdem werden Stringwerte auf Originalkomponenten berechnet und können bei echten
Übersetzungen niedrig sein. Kein Threshold oder Gewicht wurde nach dem Lauf optimiert;
die Standardpipeline bleibt unverändert. Eine unabhängige Bewertung steht aus.

Rohdaten: `results/component-evidence-laboratory-20261119.json.gz`,
`results/component-evidence-targeted-20261119.json.gz`,
`results/component-evidence-control-20261119.json.gz`.
Nachgerechnete Metriken und Regelbeiträge: `results/component-evidence-summary-20261119.json`.
Die gespeicherten Merkmale reproduzieren die gewichteten Scores exakt; alle öffentlichen
Matrixausgaben wurden gegen das unveränderte Schema geprüft.

#### Vergleich 25 % String / 75 % Embedding am 20.11.2026

Nur `string_weight` der gewichteten Fusion wurde von 0,5 auf 0,25 geändert;
Lexikongewicht 0,3, Regeln, Threshold 0,5, Seed 42 und Daten blieben gleich.
Identische Komponentenmerkmale wurden zwischen den Läufen nachgeprüft.
Die ungewichtete Komponenten-Basis bleibt als eigene 50:50-Referenz erhalten.

| Datensatz / Gewichtung | TP | FP | FN | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Geänderte Laborlabels, 50:50 | 104 | 488 | 88 | 0,176 | 0,542 | 0,265 |
| Geänderte Laborlabels, 40:60 | 106 | 490 | 86 | 0,178 | 0,552 | 0,269 |
| Geänderte Laborlabels, 25:75 | 105 | 490 | 87 | 0,176 | 0,547 | 0,267 |
| Geänderte Laborlabels, 20:80 | 105 | 503 | 87 | 0,173 | 0,547 | 0,263 |
| 33 Kontrollszenarien, 50:50 | 31 | 12 | 12 | 0,721 | 0,721 | 0,721 |
| 33 Kontrollszenarien, 40:60 | 31 | 13 | 12 | 0,705 | 0,721 | 0,713 |
| 33 Kontrollszenarien, 25:75 | 31 | 16 | 12 | 0,660 | 0,721 | 0,689 |
| 33 Kontrollszenarien, 20:80 | 31 | 19 | 12 | 0,620 | 0,721 | 0,667 |

Im Labor werden zwei richtige neu erkannt, einer geht verloren und zwei falsche kommen
hinzu. Die kleine 24-Paar-Probe bleibt unverändert (TP/FP/FN 5/10/0). Der höhere
Embedding-Anteil bringt somit keinen konsistenten Vorteil bei diesen bekannten Daten.
Es gab keine technischen Fehler und keine nachträgliche Parameteranpassung.

Rohdaten: `results/component-evidence-{laboratory,control,targeted}-2575-20261120.json.gz`.
Direkte Gegenüberstellung und Entscheidungsänderungen:
`results/component-evidence-2575-comparison-20261120.json`.

40:60 und 20:80 wurden anschließend nur durch Neuberechnung der Fusion auf denselben
gespeicherten Komponentenmerkmalen geprüft, ohne Modelle erneut auszuführen. Beide
Varianten sind als `component_evidence_40_60` und `component_evidence_20_80` im JSON-Baukasten
verfügbar; 25:75 bleibt unverändert eingestellt. Gegenüber 25:75 gewinnt 40:60 im Labor
einen richtigen Treffer ohne zusätzliche falsche, 20:80 erzeugt dagegen 13 zusätzliche
falsche ohne weiteren richtigen Treffer. Die kleine Probe bleibt für alle Gewichte
unverändert (5/10/0). Ergebnisse, Parameter, Quellhashes und neue Entscheidungsmatrizen:
`results/component-evidence-weights-20261120.json`. Fusionszeiten dieses Nachrechnens
enthalten keine Modellberechnung und sind nicht als End-to-End-Laufzeiten vergleichbar.

#### Systematisches Raster: 64 Kombinationen

`mixes[].option_grid` erweitert eine Komponentenfusion im bestehenden Baukasten:
vier Stringgewichte (0,5/0,4/0,25/0,2), vier Lexikongewichte (0/0,1/0,2/0,3),
Synonymbonus und Gegenrelationsregeln unabhängig an/aus. Das ergibt 64 Einstellungen.
Bereits vorhandene gleichwertige Definitionen werden wiederverwendet, nicht dupliziert.
Die alten Optionsnamen bleiben gültig: `rules: false` deaktiviert weiterhin beide Regeln;
bei `rules: true` steuern `synonym_rule` und `relation_rules` die Regeln einzeln.
Mindestscore 0,9, Gegenrelationsgrenze 0, Seed 42 und Threshold 0,5 bleiben fest.

Ein Befehl berechnet alle 64 Fusionen auf bereits gespeicherten Komponentenmerkmalen:

```bash
PYTHONPATH=src .venv/bin/python -m research.sweep_component_weights \
  --features results/component-evidence-laboratory-2575-20261120.json.gz \
  --output results/component-evidence-grid-laboratory.json.gz
```

Die Eingabedatei liefert Daten, Modelle und Merkmale; aktuelle Gewichte/Regelschalter
kommen aus `research/experiments.json` (optional `--config`). Es werden keine Modelle
geladen oder Texte neu vorverarbeitet. Der normale `research.compare` unterstützt das
Raster ebenfalls, berechnet dabei aber die gemeinsamen Merkmale einmal neu.
Dateien werden nicht überschrieben. Historische Modell-/Baselinezeiten sind nicht mit
den neuen reinen Fusions-/Zuordnungszeiten vergleichbar.

Die 64 Einstellungen wurden auf allen drei bekannten Entwicklungsdatensätzen geprüft.
Beste Einstellungen nach F1, Precision und Recall, **nicht unabhängig validiert**:

| Datensatz | String/Embedding | Lexikongewicht | TP | FP | FN | Precision | Recall | F1 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Geänderte Laborlabels | 25:75 oder 20:80 | 0 % | 106 | 488 | 86 | 0,178 | 0,552 | 0,270 |
| 33 Kontrollszenarien | 50:50 | 0 % | 33 | 11 | 10 | 0,750 | 0,767 | 0,759 |
| Kleine 24-Paar-Probe | alle vier Verhältnisse | 0 % | 5 | 5 | 0 | 0,500 | 1,000 | 0,667 |

Die Regelschalter ändern in diesem Raster weder Threshold-Entscheidungen noch Top-1.
Der Synonymbonus kann einzelne Scores verändern; ausreichend eindeutige Gegenrelationen
fehlen für einen Entscheidungsgewinn. Unter den 64 Parametereinstellungen gibt es nur
14 unterschiedliche Entscheidungsmuster im Labor, elf im Kontrollsatz und vier in der
kleinen Probe. Gleichstände sind daher keine 64 unabhängigen Qualitätsnachweise.

Lexikongewicht 0 ist hier jeweils am besten, aber keine Einstellung gewinnt auf allen
Aufgaben. Gegenüber der Embedding-Referenz gehen im Labor weiterhin viele richtige
Treffer verloren; die bekannten Probleme werden durch Gewichtstuning allein nicht gelöst.
Die Ergebnisse flossen weder in Training noch in eine automatische Standardauswahl ein.
Diese wiederholt betrachteten Daten sind Entwicklungsdaten und kein unabhängiger Test.

Die vollständigen Optionen, Matrizen, Entscheidungen, Metriken und Quellen liegen in
`results/component-evidence-grid-{laboratory,control,targeted}-20261120.json.gz`.
`results/component-evidence-grid-summary-20261120.json` enthält alle 64 Ergebnisse pro
Datensatz, Gleichstände, Regelbeiträge sowie entfernte falsche und verlorene richtige
Treffer relativ zur Embedding-Referenz. Kandidaten-Top-1 wird zusätzlich ohne triviale
Ein-Kandidaten-Fälle ausgewiesen. Merkmalsquelle und aktuelle Fusionsquellen sind gehasht;
alle neuen Scores wurden aus den gespeicherten Merkmalen exakt nachgerechnet.
Standardpipeline und aktueller 25:75-/30%-Lexikon-Default bleiben unverändert.

### Explizite Relationsmerkmale (Einzelwerte)

Unter `methods.wordnet` und `methods.odenet` aktiviert `relation_features` die
zusätzlichen numerischen Matrizen; eine leere Merkmalsliste schaltet sie ab.
Oberbegriffe werden durch `Synset.closure('hypernym', 'instance_hypernym')`
ermittelt. Die eigene Graphsuche und die Option `relation_depth` sind entfernt.
Sie nutzen dieselben vorbereiteten Labels und denselben Lexikonleser wie die
Synsetsuche. Abfragen werden je Label bzw. Synset wiederverwendet.

| Merkmal | Bedeutung |
| --- | --- |
| `pair_known` | Beide Labels haben mindestens einen Synseteintrag. |
| `reference_synset_count` | Anzahl möglicher Referenzlesarten, unskaliert. |
| `student_synset_count` | Anzahl möglicher Schülerlesarten, unskaliert. |
| `reference_hypernym` | Eine Referenzlesart ist ein Oberbegriff einer Schülerlesart. |
| `reference_hyponym` | Eine Referenzlesart ist ein Unterbegriff einer Schülerlesart. |
| `antonym` | Explizite Antonymrelation zwischen Synsets oder den tatsächlich gefundenen Wortlesarten. |
| `path_similarity` | Native `wn.similarity.path`, Maximum über verbundene Nomen-/Verb-Lesarten. |
| `wup_similarity` | Native `wn.similarity.wup`, ebenfalls maximiert über mögliche Lesarten. |
| `taxonomy_available` | Mindestens ein Nomen-/Verb-Lesartenpaar konnte mit beiden Metriken ausgewertet werden. |

Die Matrizen stehen unter `features[].relation_features` und werden bereits im
Matching-Kern berechnet; der Forschungslauf übernimmt sie unverändert. Die Zusatzlaufzeit
steht separat unter `relation_seconds`. Der bestehende gemeinsame Synsetscore
bleibt unter `features[].scores`; er wird nicht als neues Verfahren dupliziert.
OpenThesaurus liefert weiterhin nur seine vorhandenen Synonymgruppen.

Diese Merkmale werden zunächst nur als Evidenz gespeichert, ohne eigene Synonymentscheidung.
Sie werden nicht automatisch gemittelt oder als Kandidatenfilter benutzt.
Im Service werden sie über `semantic_features` explizit ausgewählt. Bei binären Relationsmerkmalen bedeutet 1
Existenz bei mindestens einer möglichen Lesart, nicht die fachlich passende Bedeutung. Mehrere Relationen
können gleichzeitig auftreten. Eine 0 beweist keine fehlende Beziehung: Labels,
Lesarten oder Relationen können im Lexikon fehlen. Auch `pair_known=1` garantiert
keine vollständigen Relationen. Path/Wu-Palmer verwenden keine simulierte Wurzel;
bei fehlender Verbindung oder ungeeigneter Wortart steht `taxonomy_available=0`.
Das Maximum wird je Metrik separat bestimmt und ist keine Lesartenauswahl.
Ein hoher ontologischer Score beweist keine Synonymie. IC-Metriken bleiben bis
zur Wahl geeigneter Häufigkeitsdaten zurückgestellt; kleine Labelmengen werden
nicht als allgemeine Bedeutungsstatistik ausgegeben.

### Sprachübergreifender Vergleich mit wn.translate

Die neue Kette `wn_translate: ["normalize", "wn_translation"]` vergleicht DE/EN
ohne maschinelles Textübersetzungsmodell. Für deutsche Labels werden mögliche
OdeNet-Synsets mit `Synset.translate(lexicon='omw-en:1.4')` auf englische Synsets
abgebildet. Englische Labels werden direkt im englischen WordNet gesucht.
Gemeinsame englische Synsets ergeben 1, sonst 0. Es wird keine erste Lesart oder
ein einzelnes englisches Ersatzwort ausgewählt. Beide Datenbestände müssen im
selben wn-Datenverzeichnis liegen. Der bestehende DE→EN-Textübersetzungspfad bleibt
als eigenes Verfahren erhalten; nur eine zusätzliche Vergleichskette wird ergänzt.
Der Vergleich steht als Funktion in `methods.py` und verwendet die gemeinsame
Matrixbildung. Der vorhandene WordNet-Zugriff cached die nativen Synsetübersetzungen.
Hierfür einmal `python scripts/download_lexicons.py --wordnet` und
`python scripts/download_lexicons.py --odenet` ausführen. Der bisherige Docker-Build
bereitet OdeNet nicht automatisch vor; der neue Vergleich wurde lokal getestet.

`features[].crosslingual_coverage` unterscheidet `linked`, `unknown`, `unlinked`
und `empty`: Ein bekannter deutscher Eintrag kann ohne englische Verknüpfung bleiben.
Leere Eingabemengen werden ohne Lexikonzugriff als `not_assessed` markiert.
Auch vorhandene ILI-Verknüpfungen bestimmen nicht die fachlich richtige Lesart.

### Gezielte Preprocessing-Vergleiche und OdeNet

Neue Vergleichsläufe speichern zusätzlich `lexicon_coverage`: eindeutige
Original-/Suchtextpaare je Lexikonkette, Fall und Ausgangssprache. `known` bedeutet
Eintrag für das ganze Label, `partial` nur bekannte Worttokens ohne ganzen Eintrag,
`unknown` keinen Eintrag und `empty` leeren Suchtext. Ein Lexikoneintrag bestätigt
noch keine fachlich passende Bedeutung. Die Tokensuche trennt an Satzzeichen und
Leerraum; sie zerlegt keine Identifier oder Komposita zusätzlich.
Die einzelnen Befunde stehen unter `features[].lexicon_coverage`, die unbekannten
Original- und Suchtexte unter `lexicon_coverage[].uncovered_labels`.
WordNet wird nach Übersetzung geprüft: Das misst die Abdeckung der englischen
Suchtexte, keine direkte deutsche Abdeckung. Nicht unterstützte Sprachen und
fehlende Ressourcen bleiben separat als nicht verfügbar ausgewiesen.
Die Diagnose verändert weder Scores noch Auswahlmasken; `coverage_seconds`
speichert ihre zusätzliche Laufzeit außerhalb der bisherigen Score-Rechenzeiten.
Gemessen wird der aktuelle Zugriff des jeweiligen Backends. Ein unbekannter
Suchtext beweist deshalb nicht, dass der Eintrag im Datenbestand fehlt.
Die erste Prüfung zeigte einen OdeNet-Zugriffsfehler: Unser eigener Normalizer
passte bei Umlauten nicht zum Suchindex von wn. OdeNet verwendet deshalb jetzt
die Standardnormalisierung von wn. Gebäude, Größe, Fläche und Gerät werden wieder
gefunden. Frühere OdeNet-Ergebnisse vor dieser Korrektur sind nur eingeschränkt
aussagekräftig; fehlende Einträge und tatsächliche Datenlücken sind zu unterscheiden.

Für die fünf vorhandenen Laborverwaltungsmodelle gibt es einen getrennten Datensatz:

```bash
python -m research.build_laboratory_cases
PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
.venv/bin/python -m research.compare --data research/laboratory-cases.json \
  --output results/laborverwaltung.json.gz
```

Der erste Befehl ist nur zum erneuten Erzeugen nach Änderungen der Quelldateien
nötig. Der Datensatz enthält Musterlösung gegen Schreibweise, Tippfehler/Abkürzungen,
Fachbegriffe, Sprachmix und Mehrdeutigkeit mit jeweils allen 48×48 Kandidaten.
Original-IDs, doppelte Labels und Zeilenumbrüche bleiben erhalten.
`annotation_policy` dokumentiert vorläufige Erwartungen anhand der Fallstudie;
gleiche IDs bedeuten nicht automatisch gleiche Bedeutung. Wiederholte gleichwertige
Labels sind mehrere positive Kandidaten, keine erzwungene 1:1-Sollzuordnung.
`changed_student_ids` und `changed_reference_ids` markieren veränderte Modellstellen.
Die Zusatzrangliste `rankings.<strategy>.changed_labels` bewertet ausschließlich
Paare mit veränderten Schülerlabels gegen alle Referenzkandidaten. Unveränderte
Schülerlabels zählen dort nicht als einfache Treffer mit. Top-1 wechselt dafür
die Blickrichtung: Für jedes veränderte Schülerlabel wird der beste Kandidat
der Musterlösung geprüft. Scores und Zuordnungsentscheidungen werden nicht neu
berechnet; auch Hungarian und Mutual Best stammen vom vollständigen Modell.
Die angezeigten Rechenzeiten gelten weiter für das vollständige Modell.
Der normale Vergleich und `research.rank_results` ergänzen diese Auswertung
automatisch, sobald Änderungsmarkierungen im Datensatz vorhanden sind.
Ältere Labor-Ergebnisse nutzen ersatzweise `changed_reference_ids`, da die fünf
Varianten dieselben IDs behalten. Die Modelle sind konstruierte
Entwicklungsfälle, keine unabhängigen studentischen Testdaten. Servicepipeline
und bisheriger synthetischer Datensatz werden dadurch nicht geändert.
Für große Modelle spart `.json.gz` Platz; es enthält dieselben vollständigen
JSON-Ergebnisse komprimiert. `research.rank_results --input` liest beide Formate.
Mit `.json` als Dateiendung wird weiterhin normales, nun kompaktes JSON geschrieben.

Die String-Verfahren vergleichen rohe und normalisierte Texte, Lowercase,
Lemmatisierung, Stemming, Identifiertrennung und Kompositazerlegung. Vergleiche
jeweils passende Paare: `normalize` gegen `lowercase`, `lowercase` gegen `lemma`
oder `stem`, `normalize` gegen `identifiers_cased` und `compounds_cased`.
Das Entfernen von Stopwörtern bleibt eine bewusst riskante String-Ablation:
Es kann Negationen und damit fachliche Unterschiede entfernen.

Wortvektoren erlauben nur Normalisierung, Lowercase, Identifiertrennung,
Kompositazerlegung und Lemmatisierung. FastText wandelt nicht mehr zusätzlich
intern in Kleinbuchstaben um: Die Kette zeigt jetzt die tatsächliche Vorbereitung.
Englisches FastText nutzt feste Ketten mit Normalisierung als Basis, Lowercase
oder Lemmatisierung nach der Übersetzung und Identifiertrennung davor. Das gilt
gleichermaßen für Greedy, optimales und bidirektionales Wort-Matching.
Alte FastText-Ergebnisse mit internem Lowercase sind daher keine cased-Baseline.
Die als `compounds_cased` bezeichnete Heuristik schreibt zerlegte Bestandteile
weiterhin klein; sie bewahrt Großschreibung nur bei unveränderten Wörtern.

Sentence-Embeddings bekommen feste Ketten statt des allgemeinen `$pre`-Rasters:
`normalize` als Basis und separat Lowercase, Lemma, Identifier- oder Kompositatrennung.
Stemming und Stopwortentfernung werden dort nicht automatisch ausgeführt.
Beim übersetzten Embedding erfolgen Lowercase und Lemma erst nach der Übersetzung;
Identifier-/Kompositatrennung dagegen davor. So bleiben die Übersetzungseingaben
bei den ersten beiden Vergleichen identisch.

OdeNet 1.4 wird direkt auf deutschen Labels getestet: gemeinsame Synsets mit/ohne
Lemma sowie Mischungen mit multilingualem Embedding (25:75, 50:50, 75:25),
OpenThesaurus, übersetztem WordNet und Strings. WordNet und OpenThesaurus erhalten
ebenfalls eine eigene Lemma-Kette. Lexikonsuchen vereinheitlichen Großschreibung
intern; dafür wird keine scheinbare Lowercase-Ablation angelegt.

Einmalig mit den Forschungsabhängigkeiten installieren und Daten laden:

```bash
python -m pip install -r requirements-research.txt
python scripts/download_lexicons.py --odenet
```

Die Daten liegen unter `.cache/lexicons/wn`; der normale Vergleichsbefehl oben
führt auch die neuen Ketten aus. Das Matching selbst lädt nichts herunter.
OdeNet-Daten: [CC BY-SA 4.0](https://github.com/hdaSprachtechnologie/odenet).
Die Ergebnisdatei speichert Konfiguration, wn-Version, OdeNet-Version und Datenhash.

Gemeinsame Synsets sind binäre Evidenz für eine mögliche gemeinsame Lesart,
keine Bedeutungsdisambiguierung. Ein Nullscore kann auch einen fehlenden Eintrag
bedeuten. Gewichtete Mittel mit Cosinus-Scores sind unkalibrierte Experimente;
fehlende Abdeckung kann den Gesamtscore senken. OdeNet basiert teilweise auf
OpenThesaurus, daher sind diese Evidenzen nicht unabhängig. Vergleiche Verfahren
nur auf denselben verfügbaren Fällen (OdeNet hier nur Deutsch). Es gibt weiterhin
keine automatische Übernahme eines Forschungssiegers in die Servicepipeline.

Die Konfiguration vergleicht mit allen Ressourcen 38 Szenarien:
28 ursprüngliche Kategorien und sechs zusätzliche schwierige Kontrastkategorien.
Testdaten mit erwarteten Paarzuordnungen stehen in `research/model-cases.json`;
`python -m research.build_model_cases` erzeugt sie aus dem Repository-Beispielmodell
und synthetischen Varianten. `examples/order-management-input.json` ist eine
Serviceeingabe mit Labels dieses Modells. Reale geprüfte Schülerabgaben fehlen.

Ein Lauf speichert **eine JSON** (Formatversion 3), keine Markdown-Berichte: Dataset,
Konfiguration, Rohscores, kombinierte Matrizen, Entscheidungen, Precision/Recall/F1, Top-1,
Laufzeiten, Seed, Modellrevisionen, Ressourcen-/Codehashes und Paketversionen.
Bestehende Dateien werden nicht überschrieben. Nicht unterstützte Sprachen werden
als nicht verfügbar markiert; technische Fehler führen zu Exitcode 1.

Top 3 je Kategorie, je **Sprachgruppe** (`de`, `de-en`, `de-es`, …) und insgesamt
erscheinen im Terminal und unter `rankings` im
JSON. Die Sprachgruppen werden aus den nichtleeren Labels der Fälle abgeleitet; Gruppen
mit wenigen Szenarien (z. B. `de-es`: 1) sind kaum aussagekräftig, die Szenarioanzahl
steht jeweils dabei. Preprocessing, Einzelmethoden und Gewichte werden ausgeschrieben,
darunter „Nicht vollständig ausgeführt“ mit Grund und Zahl der betroffenen Läufe.
Dateihashes der Wortvektormodelle stammen aus dem Download-Manifest
(`.cache/word-vectors/huggingface-download-manifest.json`), wenn Pfad und Dateigröße
passen (`sha256_source: manifest`); sonst werden sie berechnet. Auf gespeicherten
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
- Rechenzeiten enthalten kein Modellladen; die Ladezeit steht getrennt in
  `model_load_seconds` und im Terminal. Geteilte Modelle (z. B. der Übersetzer) werden
  dem ersten Verfahren zugerechnet, das sie braucht; spaCy-Ladezeiten sind nicht
  getrennt. Das sind keine End-to-End-Latenzen; Kandidatenaufbau und
  JSON-Konvertierung sind ausgeschlossen.
- „Bank/Bank“ mit verschiedener Bedeutung bleibt ohne Kontext unlösbar. Die
  Kandidatenheuristik nutzt Konkurrenz in der Matrix, keine Graphstruktur.


## Docker und Tests

Im Serviceverzeichnis:

```bash
docker build -t modeling-copilot/synonym-matching-louis:latest .
docker run --rm --network none -i modeling-copilot/synonym-matching-louis:latest < examples/order-management-input.json
python -m pytest -q
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 RUN_MODEL_TESTS=1 RUN_LEXICON_TESTS=1 python -m pytest -q
```

Das Image lädt Abhängigkeiten, Standardmodelle, DE/EN-spaCy-Modelle und Lexika beim
Build. Ein Container verarbeitet eine Eingabe und endet. Daten bleiben im Image,
RAM-Caches nur im Prozess. Andere Modelle benötigen ein entsprechend vorbereitetes
Image. Die Standardmodelle sind auf feste Hugging-Face-Commits gepinnt
(`EMBEDDING_REVISIONS` in `methods.py`, `TRANSLATION_REVISION` in `translation.py`);
bei eigenem `model` gilt weiter `main`. Geladene Revisionen werden
in Experimenten dokumentiert. Die Dagu-Datenübergabe ist weiterhin Demo-Stand und
muss vom aufrufenden Dienst angepasst werden.

**Modelle und Speicherplatz** (drei verschiedene Dinge nicht verwechseln):

- *Modellgewichte im Image:* nur die drei Standardmodelle im Hugging-Face-Cache
  (`HF_HOME=/app/.cache/huggingface`, etwa 1,1 GB: multilinguales MiniLM, all-MiniLM-L6-v2,
  Opus-MT DE→EN), jeweils genau einmal. `pip` läuft mit `--no-cache-dir`.
- *Forschungsmodelle:* Word2Vec/FastText liegen nur lokal unter `.cache/word-vectors/`
  (ca. 14 GB, je Modell eine Datei per `hf download --local-dir`). Sie sind per
  `.dockerignore` und fehlendes `COPY` nie im Image. Nicht zusätzlich in den
  Hugging-Face-Cache laden.
- *Berechnete Ergebnisse:* der Label-Cache für Übersetzungen und Embeddings
  (`cache.py`) liegt nur im Prozessspeicher und ist unabhängig von den Gewichten.
- `fasttext` und `gensim` stehen in `requirements-research.txt` und nicht im Image.

Lexikonquellen: [WordNet über wn](https://github.com/goodmami/wn),
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

Aktivierung: Die Wortvektor- und Ranking-Einträge stehen bereits in
`research/experiments.json` und laufen im normalen Vergleichsbefehl mit
(`"enabled": false` schaltet sie ab):

```bash
PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
.venv/bin/python -m research.compare --output results/vergleich.json
```

Fehlende Vektoren ergeben **nicht verfügbar**, keine erfundenen
Scores oder Qualitätserfolge.

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
oder heruntergeladen. Die Modelle stehen mit Pfad, Quelle und Revision in
`research/experiments.json` unter `methods`.
Pfade beziehen sich auf das Serviceverzeichnis. Nur vorhandene Modelle eintragen.
Für reine Vektordateien wird Gensim bei Bedarf importiert; vollständige
FastText-Binärmodelle nutzen den nativen FastText-Loader:

```bash
.venv/bin/python -m pip install -r requirements-research.txt
```

Unterstützt: `word2vec_text`, `word2vec_binary`, `fasttext_bin` (mit Subwords),
`glove` (Text ohne Header). Die kleinen Vektoren der Tests prüfen nur die
Funktion und sind kein Qualitätsbenchmark.
FastText-Textvektoren enthalten keine Subword-Informationen; nur ein vollständiges
FastText-Binärmodell kann unbekannte Wörter über Subwords repräsentieren.

Getrennte Sprachdateien müssen im selben ausgerichteten Raum liegen und benötigen
`aligned: true`. Gleiche Dimension allein reicht nicht. Alternativ steht in der Kette
der Schritt `translate` (DE→EN) vor dem englischen Wortvektor-Verfahren
(`["$pre", "translate", "fasttext_en_matching"]`).
Andere Sprachen als de/en werden dabei nicht unterstützt (nicht verfügbar).
Englische Labels bleiben unverändert. Die Übersetzung wird über alle Verfahren
hinweg wiederverwendet.

Optionen je Modell: das Preprocessing kommt aus der Kette (`$pre` für alle Pipelines
in `experiments.json`, wie bei den Stringverfahren),
`lowercase` (Standard true, passend zum Vokabular des Modells und nach der Kette
angewendet), `nouns_only` (Standard false), `delta` (Standard 0.2) und `matching`:
`greedy` (Standard, siehe oben), `optimal` (die 1:1-Wortpaare maximieren die Summe,
Hungarian auf Wortebene) oder `bidirectional` (jedes Wort sucht sein bestes Gegenstück,
Mittel beider Richtungen, nicht 1:1, symmetrisch). Eine Variante eines Modells schreibst
du mit `"based_on"`: `{"based_on": "fasttext_de_matching", "matching": "optimal"}`
übernimmt Dateien und Optionen; das Modell wird für Varianten mit denselben Dateien
nur einmal geladen. Bei den kurzen Labels (1–3 Wörter) ergaben `greedy` und `optimal`
in den synthetischen Fällen praktisch dieselben Werte.
Jedes Modell wird einmal geladen, für alle Preprocessing-Varianten verwendet und
danach freigegeben. Die frühere feste Vorverarbeitung (normalize, split_identifiers)
entspricht der Pipeline `identifiers_cased`; die Ergebnisse stimmen mit den früheren
Einzelläufen überein.
Nomenfilterung nutzt die vorhandenen DE/EN-spaCy-Modelle und kann als eigene
Ablation in einem separaten Lauf aktiviert werden. Bei Übersetzung wird POS im
englischen Zieltext bestimmt. Für einen fairen Vergleich die Vorverarbeitung
zwischen Vektormodellen gleich halten. Die vollständigen Optionen werden gespeichert.

Ein weiteres Modell ist ein neuer Eintrag mit `files`, `format`, Quelle und Revision
unter `methods`, eine Kette dafür unter `chains` und optional eine Mischung unter
`mixes`; der Befehl bleibt gleich.

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

Historischer Erstlauf (die Ressourcen sind lokal inzwischen gelöscht, da sie nicht
von Hugging Face stammten; die Verfahren GloVe, Paragram sowie englisches Word2Vec
sind in `experiments.json` nicht mehr enthalten und der Lauf ist so nicht
reproduzierbar). Es wurden lokal folgende englische 300D-Vektoren bereitgestellt:
`word2vec-google-news-300`, `fasttext-wiki-news-subwords-300` (statischer Export),
`glove-wiki-gigaword-300` und `Paragram-SL999-300`. Deutsche Labels werden vorher
mit dem vorhandenen Übersetzungsmodell ins Englische übersetzt. Alle vier Pfade
verwenden `normalize`, `split_identifiers`, danach Übersetzung und Lowercasing;
kein Nomenfilter, `delta=0.2`. Die Fusion nutzt gleiche Gewichte, Threshold 0.5.
Spanische Fälle sind für diese Pfade nicht verfügbar und werden bei einem
gemeinsamen Vergleich ausgeschlossen. Das ist ein synthetischer Diagnoselauf,
kein unabhängiger Nachweis der besten Pipeline.

Modellnamen, Optionen und SHA256-Dateihashes werden im Ergebnis gespeichert.
Modelle werden nacheinander geladen und nach der Rohscoreberechnung freigegeben.
Wortmodelle laufen vor den Sentence-Embeddings. Der native FastText-Loader
vermeidet Gensims zusätzliche Matrixkopien und die vorberechneten Vektoren für
den gesamten Wortschatz; abgefragt werden nur die benötigten Wörter.
Ungültige UTF-8-Bytes in einzelnen Vokabelschlüsseln werden beim Einlesen durch
das Unicode-Ersatzzeichen ersetzt; die Vektoren bleiben unverändert.

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

Drei Hugging-Face-Wortvektormodelle sind in `research/experiments.json` konfiguriert;
die Servicepipeline bleibt unverändert. Die Ressourcen liegen nach dem Download lokal
unter `.cache/word-vectors/` und werden nicht mit Git versioniert.
Die ersten synthetischen Diagnoseläufe sind unten zusammengefasst.

| Verfahren in `experiments.json` | Vergleich | Ressourcen |
| --- | --- | --- |
| `word2vec_de_matching` | Deutsches Word2Vec ohne Übersetzung | ca. 738 MB |
| `fasttext_de_matching` | Deutsches FastText ohne Übersetzung | ca. 7.24 GB |
| `fasttext_en_matching` | DE→EN-Übersetzung + englisches FastText | ca. 7.24 GB |

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

Nach Bereitstellung der Dateien läuft alles mit dem einen Befehl aus dem Abschnitt
„Forschung: ein Vergleichslauf“; ohne Datei ergibt das jeweilige Verfahren
„nicht verfügbar“. Die früheren Einzelläufe je Profil und das manuelle Zusammenführen
entfallen.

Nur identische Fallmengen bei Threshold 0.5 vergleichen: deutsche Modelle und
Übersetzungspipeline auf rein deutschen Mengen; die Übersetzungspipeline kann
zusätzlich gemischte DE/EN-Mengen verarbeiten. Spanisch bleibt hier nicht verfügbar.
Precision, Recall, F1, Top-1 und Laufzeit werden vom vorhandenen Runner gespeichert,
ebenso Modellkonfigurationen und Dateihashes. GloVe/Paragram sind nicht mehr enthalten.

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
# Kontrollierter Vergleich der Lexikonquellen

`research/compare_component_lexicons.py` vergleicht vier in
`experiments.json → component_lexicon_comparison` konfigurierte Quellen:

- `translated_wordnet`: bisherige maschinelle Übersetzung und englisches `omw-en:1.4`.
- `native`: Deutsch direkt über `odenet:1.4`, Englisch direkt über WordNet.
  Ein direktes DE/EN-Paar ist hier nicht vergleichbar, nicht widerlegt.
- `ili`: Originalbegriffe nachschlagen und deutsche Synsets/Senses mit den nativen
  `wn.translate()`-Funktionen in das englische WordNet abbilden.
- `combined`: Merkmale aus übersetztem WordNet und nativer Quelle zusammenführen.
  Synonymie-/Gegenrelationskonflikte bleiben diagnostisch sichtbar; für die Fusion
  wird die widersprüchliche Lexikonevidenz neutralisiert. Keine neue Fusionsformel.

Die vorhandene Zerlegung, Teilzuordnung und String-/Embedding-Scores werden aus
einem gespeicherten Komponentenlauf übernommen und auf Gleichheit geprüft.
Keine Modelle werden neu geladen. Die Fusion bleibt für alle vier Quellen gleich:
25 % String / 75 % Embedding, 30 % Lexikonanteil, beide Evidenzregeln aktiv.
Fehlende Einträge und fehlende ILI-Verknüpfungen werden separat gespeichert.
Die Mehrdeutigkeit der Ausgangswörter bleibt auch nach ILI-Abbildung berücksichtigt.
Die Ontologie bleibt ein diagnostisches Merkmal; keine zusätzliche Synonymbestätigung.

```bash
PYTHONPATH=src .venv/bin/python -m research.compare_component_lexicons \
  --features results/component-evidence-laboratory-2575-20261120.json.gz \
  --output results/mein-lexikonvergleich.json.gz
```

Ein neuer Ausgabename verhindert das Überschreiben vorhandener Ergebnisse.
Beide Lexika müssen bereits lokal vorhanden sein. `summary` enthält alle Fälle,
`changed_labels` separat nur geänderte Schülerlabels gegen alle Referenzkandidaten.
Die gespeicherten Entscheidungen umfassen Threshold, Mutual Best und Hungarian.
Laufzeitdaten messen nur die gemeinsame neue Lexikonarbeit; Modellzeiten werden
nicht erneut gemessen. Nullwerte in Ranking-Zeitfeldern bedeuten hier ungemessen.

Ergebnisse vom 20.11.2026 bei Threshold 0,5; Format **F1 / falsche Treffer**:

| Lexikonquelle | Geänderte Laborlabels | Kontrollfälle | Gezielte Zerlegungsfälle |
|---|---:|---:|---:|
| Übersetztes WordNet | 0,267 / 490 | 0,689 / 16 | 0,500 / 10 |
| Native Lexika | 0,274 / 489 | 0,711 / 15 | 0,556 / 8 |
| ILI-Verknüpfung | 0,274 / 489 | 0,717 / 16 | 0,556 / 8 |
| Beide Quellen | 0,265 / 490 | 0,703 / 16 | 0,500 / 10 |

Artefakte: `results/component-lexicons-{laboratory,control,targeted}-final-20261120.json.gz`.
Die Verbesserung ist klein und auf bekannten Entwicklungsdaten gemessen.
Sie behebt die schlechte Qualität des Komponentenansatzes nicht. Historische
Baselines, Servicekonfiguration und Outputschema bleiben erhalten. Die neuen
Quellen werden zunächst ausschließlich in diesem Forschungslauf verglichen.

## Ganzlabels mit Komponenten kombinieren

`experiments.json → whole_component_comparison` definiert die Ganzlabelgewichte
100 %, 75 %, 50 %, 25 % und 0 % sowie die drei Eingabe-/Ausgabepaare für Labor-,
Kontroll- und gezielte Zerlegungsfälle. Ein Befehl vergleicht alle fünf Gewichte
auf allen drei Datensätzen anhand gespeicherter Merkmale:

```bash
PYTHONPATH=src .venv/bin/python -m research.compare_whole_components
```

Vor einem erneuten Lauf neue Ausgabenamen in der JSON-Konfiguration wählen.
Vorhandene Ergebnisse werden nicht überschrieben. Die gespeicherten Quellen
müssen lokal vorliegen; alternativ lassen sich diese Pfade in JSON ändern.

Beide Zweige berechnen 25 % String-Ensemble (Levenshtein, Jaro-Winkler,
Zeichen-Trigramme) plus 75 % übersetztes monolinguales Sentence-Embedding.
Dann gilt `combinedScore = w * Ganzlabelscore + (1-w) * Komponentenscore`.
Keine Lexikonfusion oder Konfliktregel: so bleibt der Zerlegungseinfluss isoliert.
Abdeckungslücken von Komposita motivieren den Versuch, werden hier aber nicht
direkt über neue Lexikonmerkmale untersucht.

Die Datensätze einschließlich IDs, Reihenfolge und Annotationen sowie Seed,
Threshold und Modellprovenienz müssen übereinstimmen. Alle Gewichte nutzen
dieselben verfügbaren Fälle und die gemeinsame Kandidatenmaske. Fehlende
erfolgreiche Merkmale werden als ausgeschlossene Fälle ausgewiesen.
Gespeichert werden beide Zweigmatrizen, alle gemischten Matrizen, Precision,
Recall, F1, Top-1-Auswertungen und Threshold-/Mutual-Best-/Hungarian-Auswahl.
Die Labor-Auswertung enthält zusätzlich nur geänderte Schülerlabels gegen
sämtliche Referenzkandidaten. Laufzeiten betreffen nur Mischen und Zuordnen;
Embedding-, Übersetzungs- und Zerlegungszeiten werden nicht neu gemessen.

Ergebnisse vom 20.11.2026 bei unverändertem Threshold 0,5; **F1 / falsche Treffer**:

| Ganzlabel / Komponenten | Geänderte Laborlabels | Kontrollfälle | Gezielte Fälle |
|---|---:|---:|---:|
| 100 / 0 | 0,769 / 56 | 0,710 / 17 | 0,533 / 6 |
| 75 / 25 | 0,678 / 44 | 0,717 / 16 | 0,533 / 6 |
| 50 / 50 | 0,514 / 123 | 0,710 / 17 | 0,588 / 7 |
| 25 / 75 | 0,336 / 343 | 0,681 / 17 | 0,526 / 9 |
| 0 / 100 | 0,270 / 488 | 0,674 / 18 | 0,667 / 5 |

Auf den Laborlabels sinken die richtigen Treffer bei 75/25 von 155 auf 121,
obwohl falsche Treffer von 56 auf 44 abnehmen. Kein Mischgewicht verbessert
dort F1 gegenüber dem Ganzlabel-Endpunkt. Die frühere vollständige Fusion
(inklusive alter Konfliktregel) bleibt separat mit F1 0,876 / 7 falschen Treffern
erhalten und ist nicht der hier verwendete Ganzlabel-Endpunkt.
Keine Fälle wurden in diesen drei Läufen ausgeschlossen. Die Ergebnisse stammen
von bekannten Entwicklungsdaten, nicht von einem unabhängigen Testdatensatz.
Keine automatische Auswahl oder Änderung der Servicepipeline.
Artefakte: `results/whole-components-{laboratory,control,targeted}-20261120.json.gz`.

### Nachvergleich mit sichtbaren Trenngrenzen

Das optionale Verfahren `component_evidence` behandelt jetzt Leerzeichen,
Unterstriche, CamelCase und Bindestriche zwischen Buchstaben konsistent als
Trenngrenzen. Die bestehende Auflösung von `Nr.` bleibt vorgeschaltet.
`Room number` und `Etagen-Nummer` werden damit zweiteilig. `E-Mail` bleibt
zusammen; Punkte, Dezimalzahlen, Versionsnummern und numerische Bindestriche
werden nicht pauschal getrennt. Die bestehende Kompositazerlegung für einzelne
unbekannte deutsche Wörter bleibt unverändert. Allgemeine Phrasen mit sichtbaren
Grenzen werden jetzt ebenfalls zerlegt, einschließlich möglicher Funktionswörter;
dies ist keine linguistische Bedeutungsanalyse oder neue Stopwortregel.

Keine Änderungen an Teilzuordnung, Mittelung, Fusion, Gewichten oder Threshold.
Die neuen Komponentenmerkmale wurden mit denselben lokalen Modellen neu
berechnet. Der Ganzlabelzweig wurde unverändert wiederverwendet.
`whole_component_comparison` verweist jetzt auf diese neuen Komponentenartefakte.

Geänderte Laborlabels, Threshold 0,5, beide Zweige ohne Lexikon-/Konfliktregeln:

| Ganzlabel / Komponenten | TP | FP | F1 |
|---|---:|---:|---:|
| 100 / 0 | 155 | 56 | 0,7692 |
| 75 / 25 | 155 | 48 | 0,7848 |
| 50 / 50 | 158 | 141 | 0,6436 |
| 25 / 75 | 162 | 532 | 0,3657 |
| 0 / 100 | 160 | 785 | 0,2814 |

Bei 75/25 werden gegenüber dem Ganzlabelzweig acht falsche Treffer entfernt,
ohne neue falsche Treffer und ohne Verlust oder Zugewinn richtiger Treffer.
Gegenüber derselben Mischung mit alter Zerlegung werden 34 richtige Treffer
zurückgewonnen; zugleich entstehen vier zusätzliche falsche Treffer.
Beispiel `RaumNr. ↔ Room number`: Mischscore vorher 0,4629, jetzt 0,5757.
Auf den Kontrollfällen bleibt die 75/25-Mischung bei F1 0,7174 / 16 FP;
auf den gezielten Fällen bleibt sie bei F1 0,5333 / 6 FP.

Die reine Komponentenbewertung bleibt problematisch: mehr Recall geht hier
mit erheblich mehr falschen Treffern einher. Die historische vollständige Fusion
mit alter Konfliktregel (F1 0,8757 / 7 FP) wird nicht übertroffen. Es sind weiterhin
bekannte Entwicklungsdaten; keine unabhängige Validierung und keine Serviceumstellung.

Neue Artefakte:
`results/component-boundaries-{laboratory,control,targeted}-20261120.json.gz`,
`results/whole-components-boundaries-{laboratory,control,targeted}-20261120.json.gz`
und `results/component-boundaries-summary-20261120.json`.

## Regelbaum auf Ganzlabels (Forschung)

```bash
PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  .venv/bin/python -m research.decision_tree
```

`experiments.json → decision_tree` enthält Datenquellen, neue Ausgabenamen,
Lexikonquellen und Schwellen. Bestehende Ausgaben werden nicht überschrieben.
Dieser Lauf verändert weder Service noch dessen Schema oder vorhandene Baselines.

Die produktive Methodenregistry, ihre Textformen, das gepinnte multilinguale
Embedding und der Textstufenadapter des Graphmatchers werden direkt gelesen.
Die Forschungsvariante importiert sie unter einem eigenen Paketnamen. Ein Modell
und sein Cache werden über alle Datensätze/Varianten geteilt. Keine neuen Modelle.
Die Baseline `text_tiers` reproduziert nur die produktive **Textentscheidung**:
keine Glossareinträge, Vergleichsquellen, Notationssegmente oder Graphstruktur.
Kanonische Gleichheit hat Vorrang vor Damerau ≥ 0,85 und Embedding ≥ 0,85;
die produktiven Ziffern-/Wortanfangsschutzregeln bleiben aktiv.
Die Grauzonengrenze 0,70 wird gespeichert, bestätigt aber allein kein Paar.

Danach werden drei Lexikonquellen mit je zwei Embeddingregeln verglichen:
`wordnet` nutzt vorhandene Ganzlabelmerkmale nach maschineller Übersetzung;
`native` nutzt OdeNet direkt für Deutsch und WordNet für Englisch;
`ili` bildet native deutsche Bedeutungen in englische Synsets/Senses ab.
Direkte sprachübergreifende Lexikonpaare ohne ILI sind unbekannt, nicht widerlegt.
Alle Varianten verwenden dieselben Labelpaare und Textscores. Keine Zerlegung.

Entscheidungsreihenfolge:

1. Leere/nicht auswertbare Paare: `not_evaluable`.
2. Gemeinsames Synset: standardmäßig `confirmed`, auch wenn zusätzlich eine
   Gegenrelation anderer möglicher Lesarten gefunden wird. Alte Reihenfolge als Ablation.
3. Ohne gemeinsame Bedeutung: explizite Gegenrelation bei beidseits genau einem
   Synset → `rejected`, bei Mehrdeutigkeit → `open`. Die frühere Ein-Synset-Bedingung
   für Synonymbestätigung bleibt ebenfalls als Vergleichsvariante.
4. Sonst produktive Textstufen/Schutzregeln auswerten.
5. `confirm` lässt die Embeddingstufe bestätigen; `open` lässt reine
   Embeddingbestätigung offen. Sonstige unzureichende Evidenz bleibt `open`.

Genau ein Synset ist nur eine konservative Näherung, keine kontextuelle
Bedeutungsdisambiguierung. Ontologische Path-/Wu-Palmer-Werte werden als
Diagnostik gespeichert, bestätigen aber keine Synonymie. Fehlende Einträge
werden niemals allein als Gegenbeweis benutzt.

Pro Variante enthält das Forschungsartefakt eine vollständige `synonymMatrix`
mit Labels/IDs, numerischen `scores`, `verdict` und `reason`. **Kein Combined
Score** und keine erfundene Wahrscheinlichkeit. `open` zählt nicht als Treffer;
offene positive Paare zählen bei Recall/F1 entsprechend als übersehen. Gespeichert
werden auch explizite Ablehnungen und Entscheidungsabdeckung. Die binäre Auswahl
wird nur intern für Precision/Recall/F1 genutzt. Aus ihr werden weder Top-1 noch
Hungarian-Zuordnungen konstruiert. Aussagen über die vollständige Graphzuordnung
oder richtige studentische Lösungen sind mit diesem Labelversuch nicht möglich.

Ergebnisse 26.11.2026, **TP / FP / F1**; Labor nur geänderte Schülerlabels gegen
alle Referenzkandidaten, Kontrollen dieselben 33 auswertbaren Szenarien:

| Variante | Laborlabels | Kontrollfälle |
|---|---:|---:|
| Produktive Textstufen ohne Lexikon | 158 / 60 / 0,7707 | 28 / 6 / 0,7273 |
| WordNet + Embeddingbestätigung | 152 / 60 / 0,7525 | 28 / 3 / 0,7568 |
| Native Lexika + Embeddingbestätigung | 160 / 60 / 0,7767 | 29 / 3 / 0,7733 |
| ILI + Embeddingbestätigung | 148 / 60 / 0,7400 | 19 / 3 / 0,5846 |
| Native Lexika, Embedding allein offen | 93 / 0 / 0,6526 | 19 / 1 / 0,6032 |

Alle Varianten erreichen auf den 24 gezielten Paaren TP 5 / FP 0 / F1 1,0.
Die kleine gezielte Menge ist kein allgemeiner Qualitätsbeleg. Historische
vollständige Fusion auf Laborlabels: TP 155 / FP 7 / F1 0,8757, einschließlich
alter Konfliktregel. Diese wird aufbewahrt und vom neuen Baum nicht übertroffen.
Alle Daten sind bekannte Entwicklungsdaten, keine unabhängige Validierung.
Artefakte: `results/decision-tree-{laboratory,control,targeted}-20261126.json.gz`
und `results/decision-tree-summary-20261126.json`.

### Optionale deutsche Modellierungsabkürzungen

Der Forschungsschritt `expand_modeling_abbreviations` ergänzt die bisherige
`Nr.`-Regel um `Anz. → Anzahl`, `Bez. → Bezeichnung`, `Beschr. → Beschreibung`
und `PLZ → Postleitzahl`. Er läuft ausschließlich bei expliziter Sprache `de`;
Englisch und unbekannte Sprache bleiben unverändert. Die Liste ist eine
experimentelle Annahme, keine garantierte Bedeutungsauflösung.
Wortgrenzen und CamelCase werden berücksichtigt: `ArtikelAnz.` kann expandieren,
`Finanz.` und `Bezirk` bleiben erhalten. Punktabkürzungen brauchen ihren Punkt.
Frei erfundene oder andere Kürzel werden nicht erraten.

Allgemeiner Baukasten: zum Beispiel
`["normalize", "split_identifiers", "expand_abbreviations", "expand_modeling_abbreviations"]`.
Der optionale Schritt ist keine neue globale Standardvorverarbeitung.
Im Regelbaum steuert `decision_tree.modeling_abbreviations` die konkrete Liste;
`{}` deaktiviert die Erweiterung. Vergleichstexte werden auf beiden Seiten
expandiert, Originalbeschriftungen und IDs in Datensatz und Matrix bleiben
erhalten. Die tatsächlich verwendeten Texte stehen unter `comparison_labels`.
Wenn sich ein Label verändert, werden auch seine WordNet-Merkmale passend zu
den expandierten Texten neu berechnet; alte Merkmale werden nicht falsch übernommen.
Übersetzungen/Embeddings bleiben pro eindeutigem Text gecacht.

`Str. → Straße` steht getrennt unter `candidate_abbreviations`. Diese Form wird
nur unter `candidate_labels` dokumentiert, nicht gescort und nicht zur Bestätigung
oder Ablehnung benutzt. Mehrdeutiges `Str.` wird damit nicht still ersetzt.
Der produktive Service und dessen bisherige `Nr.`-Regel sind unverändert.

Nachvergleich mit direkten Lexika und Embeddingbestätigung:

| Daten | Vorher TP / FP / F1 | Mit Erweiterung TP / FP / F1 |
|---|---:|---:|
| Geänderte Laborlabels | 160 / 60 / 0,7767 | 176 / 68 / 0,8073 |
| Kontrollfälle | 29 / 3 / 0,7733 | 29 / 3 / 0,7733 |
| Gezielte Fälle | 5 / 0 / 1,0 | 5 / 0 / 1,0 |

Auf Laborlabels: 16 zusätzliche richtige und acht zusätzliche falsche Treffer,
keine verlorenen richtigen Treffer. Von den neuen Kürzeln kommt in diesen
Benchmarks nur `Bez.` vor. Für die übrigen Kürzel gibt es gezielte Funktionstests,
noch keinen fachlichen Qualitätsnachweis. Bekannte Entwicklungsdaten; keine
unabhängige Validierung und keine automatische Auswahl einer neuen Servicepipeline.
Artefakte: `results/decision-tree-abbreviations-{laboratory,control,targeted}-20261126.json.gz`
und `results/decision-tree-abbreviations-summary-20261126.json`.

## Kontrollierter Sprachpfadvergleich

```bash
PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  .venv/bin/python -m research.compare_language_paths
```

`language_path_comparison` in `experiments.json` legt Korpus und neuen Ausgabepfad
fest. Bestehende Ausgaben werden nicht überschrieben. Es gibt keine Änderung
am Servicevertrag und kein neues `language`-Attribut. Die drei Testgruppen sind
im Experiment bekannt; Spracherkennung wird nicht getestet oder vorausgesetzt.

`language-path-cases.json` enthält 27 parallel formulierte synthetische Fälle:
24 isolierte Paare und drei vollständige Kandidatenmengen, insgesamt 62
Paarvorkommen (22 positiv, 40 negativ). Die DE-/EN-Fassungen haben identische
IDs, Reihenfolgen und Annotationen. Die englischen Fassungen wurden unabhängig
vom Übersetzungsmodell formuliert, aber nicht von unabhängigen Fachexperten
validiert. Fachliche Gleichwertigkeit gilt innerhalb der angenommenen Aufgabenrollen.
Keine Trainingsdaten, keine Gewichtungs- oder Schwellenoptimierung auf diesen Fällen.

Verglichen werden A: Deutsch/OdeNet, B: Englisch/WordNet und C: dieselben
deutschen Texte wie A, maschinell ins Englische übersetzt/WordNet.
Die Lexikonsuche verwendet normalisierte Ganzlabels, ohne zusätzliche Zerlegung,
Lemmatisierung oder neue Abkürzungsexpansion. Die unveränderten produktiven
Textformen werden separat für die String-/Embedding-Zweige verwendet.
A und C teilen exakt dieselben deutschen Textscores: Nur der Lexikoneingang
ändert sich. B verwendet die unabhängig formulierten englischen Labels.

Die Auswertung trennt Textstufen ohne Lexikon, nur sichere Lexikonregeln und
den gesamten Regelbaum. Lexikonregeln verlangen weiterhin beidseits genau ein
Synset; das ist keine Bedeutungsdisambiguierung und kann ein besser abgedecktes,
aber mehrdeutigeres Lexikon stärker einschränken. Offene Paare sind keine Treffer.
Es werden keine binären Urteile als Top-1-Rangliste oder Graphzuordnung ausgegeben.

Ergebnisse 26.11.2026 auf dieser kleinen Parallelstichprobe:

| Pfad | Lexikonabdeckung¹ | Nur Lexikon TP / FP / F1 | Gesamtbaum TP / FP / F1 |
|---|---:|---:|---:|
| A: Deutsch → OdeNet | 26/40 (65 %) | 5 / 0 / 0,3704 | 16 / 2 / 0,8000 |
| B: Englisch → WordNet | 27/40 (67,5 %) | 4 / 0 / 0,3077 | 9 / 0 / 0,5806 |
| C: Deutsch → Übersetzung → WordNet | 26/40 (65 %) | 4 / 0 / 0,3077 | 13 / 2 / 0,7027 |

¹ Mindestens ein Eintrag pro eindeutigem Originaltext, keine Garantie passender
Bedeutung. Mehrfach vorkommende Texte werden für die Abdeckung nur einmal gezählt.
Gemeinsame Synsets ohne Eindeutigkeitsfilter: A 16, B 10, C 11 Paarvorkommen.
Textstufen allein: A/C TP 12 / FP 3 / F1 0,6486; B TP 8 / FP 1 / F1 0,5161.
Die Unterschiede der Gesamtbäume sind damit nicht ausschließlich Lexikonunterschiede.

Beispiele: OdeNet bestätigt `Etage ↔ Stockwerk`; die Übersetzung erzeugt
`Floor ↔ Floor`, dessen mehrere englische Lesarten die harte Synsetregel blockieren.
`Bestelung` wird vom Übersetzungsmodell zu `Beverage`: Tippfehler können also
falsche Übersetzungen erzeugen. Das rechtfertigt keine automatische Ablehnung.
Die Übersetzung verbessert den deutschen Baum hier nicht gegenüber direktem OdeNet.
Die Ergebnisse beweisen weder eine allgemeine Überlegenheit deutscher Labels
noch die Verlässlichkeit einer zukünftigen Spracherkennung.

40 deutsche Originaltexte wurden gebündelt einmal übersetzt; circa 0,22 s
Übersetzungsberechnung plus circa 0,84 s Modellinitialisierung in diesem Lauf.
Alle Modelle waren lokal vorhanden. Initialisierung und erste Berechnungen sind
getrennt gespeichert. Gemeinsame Caches und Ausführungsreihenfolge verhindern
eine Interpretation als isolierter Kaltstartvergleich; Zeiten sind keine Zusage
für andere Hardware. Ein Modell und eindeutige Texte werden wiederverwendet.
Vollständige Übersetzungen, Rohmerkmale, Entscheidungen, Versionen und Hashes
stehen in `results/language-path-comparison-20261126.json.gz`.

### Historischer vierter Pfad: wn.translate und aktive Taxonomiemerkmale

Nach diesem Vergleich wurde der ILI-Pfad auf Wunsch aus den aktiven
Sprachvergleichsläufen und Regelbaumkonfigurationen entfernt. Aktiv bleiben
direktes OdeNet, direktes WordNet und maschinelle Übersetzung → WordNet.
Die unten stehenden Vierpfad-Ergebnisse bleiben historisch erhalten; neue
Dreipfad-Läufe schreiben `results/language-path-taxonomy-20261126.json.gz`.
Die bereits vorhandenen ILI-Hilfsfunktionen bleiben für die Reproduzierbarkeit
älterer Experimente erhalten, werden in diesen aktiven Läufen aber nicht aufgerufen.

Der Sprachvergleich enthält zusätzlich D: dieselben deutschen Eingaben wie A/C,
OdeNet-Synsets/Senses über `wn.translate()`/ILI auf englische Bedeutungen abbilden.
Kein maschinell übersetzter Text wird für D verwendet. Die ursprüngliche
Mehrdeutigkeit bleibt durch die bestehenden Quell-/Zielsynset-Zählwerte erhalten.
Alle Pfade bleiben erhalten; keine neue Sprachangabe im Eingabevertrag.

`language_path_comparison.taxonomy_guard` legt vorläufige Pilotgrenzen fest:
`path_similarity: 0.25`, `wup_similarity: 0.8`. Neben dem unveränderten Baum
werden nur Path, nur Wu-Palmer und beide Werte zusammen ausgewertet.
Die Werte sind keine Wahrscheinlichkeiten und nicht auf einem unabhängigen
Validierungssatz kalibriert. Es wird keine nachträgliche Schwellenoptimierung
auf diesen Fällen vorgenommen.

Die zusätzliche Regel greift ausschließlich bei einer sonst erfolgenden
Embeddingbestätigung, beidseits genau einem Synset und vorhandener Taxonomieverbindung.
Liegt ein verwendeter Wert unter der Pilotgrenze, bleibt das Paar `open` statt
automatisch bestätigt zu werden. Hohe Werte bestätigen niemals allein;
explizite Gegenrelationen behalten Vorrang. Fehlende/unverbundene Taxonomie
und mehrere mögliche Bedeutungen werden nicht als negative Evidenz ausgelegt.
Damit wird optimistische Maximierung über verschiedene Lesarten nicht zur
harten Taxonomieentscheidung herangezogen.

Ergebnis auf denselben 62 Paarvorkommen:

| Pfad | Nutzbare Lexikonabdeckung | Baum TP / FP / F1 | Mit Path + Wu-Palmer |
|---|---:|---:|---:|
| A: DE → OdeNet | 26/40 | 16 / 2 / 0,8000 | unverändert |
| B: EN → WordNet | 27/40 | 9 / 0 / 0,5806 | unverändert |
| C: DE → MT → WordNet | 26/40 | 13 / 2 / 0,7027 | unverändert |
| D: DE → OdeNet → ILI → WordNet | 24/40 | 13 / 2 / 0,7027 | unverändert |

Die Einzelablationen ändern ebenfalls keine Entscheidung. Für A/B gibt es keine
Embeddingbestätigung, die zugleich die Eindeutigkeits- und Verfügbarkeitsbedingungen
der neuen Regel erfüllt. Für C/D gibt es je zwei Vorkommen des falschen Paars
`Nachname ↔ Vorname`: Path 0,3333 und Wu-Palmer 0,8571 liegen beide über den
Pilotgrenzen. Das zeigt unmittelbar, dass hohe Taxonomienähe keine fachliche
Gleichwertigkeit beweist. Auf dieser Stichprobe ist kein Zusatznutzen belegt.

Bei D sind 26 deutsche Texte bekannt, aber nur 24 über ILI verknüpft. Bei
`Bestellnummer` und `Best.-Nr.` fehlt hier die Verbindung. D kann andererseits
`Etage ↔ Stockwerk` gezielter als die maschinelle Übersetzung auf dieselbe
englische Bedeutung abbilden. Der Gesamtnutzen ist nicht größer: C und D haben
gleiche TP/FP, aber fünf unterschiedliche konkrete Urteile (einschließlich
offen/abgelehnt). Die 243 bisherigen A/B/C-Entscheidungsdatensätze wurden exakt
reproduziert. Weitere Dokumentation und Grenzen des Parallelkorpus gelten fort.

Artefakte: `results/language-path-taxonomy-ili-20261126.json.gz` und
`results/language-path-taxonomy-ili-summary-20261126.json`.
Der gleiche Befehl `python -m research.compare_language_paths` nutzt den aktuellen
Dreipfad-Ausgabepfad aus JSON; vorhandene Artefakte werden weiterhin nicht überschrieben.

### Ablation: gemeinsame Bedeutung ohne Ein-Synset-Beschränkung

`decision_tree.require_single_synset` ist standardmäßig `false`: Ein gemeinsames
Synset kann auch bei mehreren Lesarten bestätigen. Varianten mit Suffix
`_single_synset` behalten die alte Bedingung bei. Die Regeln für Gegenrelationen,
Widersprüche und Taxonomie bleiben absichtlich unverändert. Insbesondere wird
eine gleichzeitig gefundene Gegenrelation bei Mehrdeutigkeit weiterhin offen
gelassen; das Abschalten betrifft ausschließlich die Synonymbestätigungsbedingung.
`shared_synset` und Synsetanzahlen selbst werden unverändert berechnet und gespeichert.

Beide Varianten wurden mit exakt denselben Eingaben, Textverfahren und Lexika
ausgeführt. 168 strenge Vergleichsdatensätze auf Labor-/Kontroll-/gezielten Fällen
reproduzieren die zuvor gespeicherten Urteile exakt. Keine Schwellenanpassung.

| Daten / Quelle / Baum mit Embeddingbestätigung | Streng TP / FP / F1 | Ohne Beschränkung TP / FP / F1 |
|---|---:|---:|
| Laborlabels, direkte Lexika | 176 / 68 / 0,8073 | 177 / 68 / 0,8101 |
| Laborlabels, übersetztes WordNet | 168 / 68 / 0,7850 | 169 / 68 / 0,7879 |
| Kontrollfälle, direkte Lexika | 29 / 3 / 0,7733 | 31 / 6 / 0,7750 |
| Kontrollfälle, übersetztes WordNet | 28 / 3 / 0,7568 | 34 / 3 / 0,8500 |
| Parallelkorpus, DE → OdeNet | 16 / 2 / 0,8000 | 21 / 4 / 0,8936 |
| Parallelkorpus, EN → WordNet | 9 / 0 / 0,5806 | 10 / 0 / 0,6250 |
| Parallelkorpus, DE → MT → WordNet | 13 / 2 / 0,7027 | 16 / 2 / 0,8000 |

Zusätzliche echte Treffer: auf Laborlabels `Versuch ↔ Experiment` (direkt) bzw.
`Etage ↔ Stockwerk` (übersetztes WordNet). Im Parallelkorpus wird jetzt auch
`Floor ↔ Storey` lexikalisch bestätigt. Die gezielten 24 Paare bleiben unverändert.
Alle Werte sind Entwicklungsdaten; unterschiedliche Datensätze nicht direkt
als gemeinsames Ranking interpretieren. Keine Aussage über endgültige Graphzuordnung.

**Diagnostizierter zusätzlicher Fehler:** Die neuen falschen OdeNet-Treffer
betreffen `Rechnung ↔ Zahlung`. Die Suche senkt intern auf `zahlung` ab. Die
wn-Standardsuche liefert dafür sowohl `Zahlung` als auch `Zählung`; das gemeinsame
Synset `odenet-2197-n` enthält `Zählung` und `Rechnung`, nicht `Zahlung`.
`reader.words('Zahlung')` findet dagegen nur den richtigen Ausdruck und
`reader.synsets('Zahlung')` nur `odenet-11821-n`. Das ist ein belegtes Problem
des normalisierten Suchpfads, kein Beleg für beabsichtigte Synonymie von Rechnung
und Zahlung. Während der Ablation wurde diese Normalisierung nicht geändert.

Artefakte: `results/decision-tree-shared-synset-{laboratory,control,targeted}-20261126.json.gz`,
`results/language-path-shared-synset-20261126.json.gz` und
`results/shared-synset-ablation-summary-20261126.json` mit allen Änderungen und Beispielen.

### Korrigierte OdeNet-Suche ohne Akzentkollisionen

OdeNet erhält jetzt die originale Groß-/Kleinschreibung nach NFC-/Leerraum-
Normalisierung. `reader.words()` wird damit zunächst auf der Originalschreibung
aufgerufen. Falls der wn-Suchindex breitere Kandidaten liefert, akzeptieren wir
nur tatsächliche Wortformen, die bis auf Großschreibung übereinstimmen.
Die Prüfung nutzt `lower()`, kein Akzententfernen und keine Gleichsetzung von
`ß` und `ss`. So bleiben Zahlung/Zählung und Maße/Masse getrennt.
`zahlung`, `Zahlung` und `ZAHLUNG` können weiterhin dieselbe belegte Form finden.
Die geprüften Formen werden gecacht und sowohl für Synsets als auch für
wortbezogene Antonymrelationen benutzt. Kein zusätzliches Sprachmodell oder Index.
Englischer WordNet-Zugriff/Morphy und String-/Embeddingvorverarbeitung bleiben
unverändert. Die Synonymbestätigung bleibt ohne Ein-Synset-Beschränkung aktiv.

Kontrollierter Nachvergleich (direkte Lexika, Embedding darf bestätigen):

| Daten | Vorher TP / FP / F1 | Korrigiert TP / FP / F1 |
|---|---:|---:|
| Geänderte Laborlabels | 177 / 68 / 0,8101 | 177 / 68 / 0,8101 |
| Kontrollfälle | 31 / 6 / 0,7750 | 31 / 3 / 0,8052 |
| Deutscher Parallelkorpus | 21 / 4 / 0,8936 | 21 / 2 / 0,9333 |

Die entfernten falschen Treffer betreffen Rechnung/Zahlung. Auf den Kontrollfällen
keine verlorenen oder neu bestätigten richtigen Treffer. Die bereits bestätigten
englischen/übersetzten WordNet-Urteile bleiben exakt erhalten. Auf den gezielten
24 Paaren bleibt TP 5 / FP 0 / F1 1,0. Die Laborqualität wird hierdurch nicht weiter
verbessert. Alle Zahlen betreffen bekannte Entwicklungsdaten, nicht neue Aufgaben.

Die echten lokalen Lexikontests für Umlautsuche, Wortformen und Zahlung/Zählung
wurden zusätzlich zu den normalen Tests ausgeführt. Historische Artefakte bleiben
unverändert. Neue Ausgaben:
`results/decision-tree-exact-odenet-{laboratory,control,targeted}-20261126.json.gz`,
`results/language-path-exact-odenet-20261126.json.gz` und
`results/exact-odenet-comparison-20261126.json`.

### Ablation: gemeinsame Bedeutung vor lesartenübergreifender Gegenrelation

`decision_tree.shared_synset_first: true` lässt die gemeinsame Bedeutung zuerst
bestätigen. Die vorherige Regel blockierte auch dann, wenn eine Ober-/Unterbegriffs-
oder Antonymrelation lediglich bei anderen möglichen Lesarten gefunden wurde.
Mit `false` bleibt diese bisherige Reihenfolge aktiv. Varianten mit Suffix
`_counter_veto` reproduzieren den Stand vor der Prioritätsänderung;
`_single_synset` behält zusätzlich die historische Ein-Synset-Bedingung bei.
Alle Einzelmerkmale bleiben erhalten. Die neue Entscheidung wird mit
`shared_synset_over_counterrelation` begründet. Dies ist eine Vorranghypothese,
keine kontextuelle Bedeutungsdisambiguierung. Ohne gemeinsames Synset bleibt
die gesamte Gegenrelationsprüfung unverändert. Keine neuen Schwellen/Gewichte.

Ergebnisse (Baum mit Embeddingbestätigung):

| Daten / Quelle | Bisher TP / FP / F1 | Gemeinsames Synset zuerst TP / FP / F1 |
|---|---:|---:|
| Geänderte Laborlabels / übersetztes WordNet | 169 / 68 / 0,7879 | 175 / 68 / 0,8046 |
| Geänderte Laborlabels / direkte Lexika | 177 / 68 / 0,8101 | 177 / 68 / 0,8101 |
| EN-Parallelkorpus / WordNet | 10 / 0 / 0,6250 | 12 / 0 / 0,7059 |
| DE-Parallelkorpus / MT → WordNet | 16 / 2 / 0,8000 | 17 / 2 / 0,8293 |

Sechs zusätzliche richtige Laborpaarvorkommen betreffen `Beginn ↔ Start` und
`Ende ↔ Schluss`. Englisch gewinnt `Begin ↔ Start` und `Invoice ↔ Bill` zurück.
Kontrollfälle, gezielte Fälle und direkter OdeNet-Parallelpfad bleiben unverändert.
Keine neuen falschen Bestätigungen oder verlorenen richtigen Treffer auf diesen
Datensätzen. 168 Gegen-Vorrang-Vergleichsdatensätze reproduzieren die vorherigen
Urteile exakt. Die historische vollständige Fusion bleibt auf Laborlabels mit
F1 0,8757 / 7 FP besser. Bekannte Entwicklungsdaten, keine allgemeine Garantie.

Artefakte: `results/decision-tree-shared-first-{laboratory,control,targeted}-20261126.json.gz`,
`results/language-path-shared-first-20261126.json.gz` und
`results/shared-first-ablation-summary-20261126.json` mit konkreten Paaränderungen.

### Embeddingvergleich: MiniLM, Jina DE/EN und E5

Aus dem Serviceverzeichnis (lokale venv):

```sh
PYTHONPATH=src TOKENIZERS_PARALLELISM=false .venv/bin/python -m research.compare_embeddings
```

Modelle und Threshold-Raster stehen unter `embedding_comparison` in
`research/experiments.json`. Bei kommenden Anpassungen werden immer mindestens
0,80 / 0,85 / 0,90 auf identischen Daten vor und nach der Änderung verglichen,
jeweils mit Precision, Recall, F1 und TP/FP/FN. Keine Modellauswahl anhand
unterschiedlicher Einzelthresholds; zusätzliche Rasterpunkte bleiben diagnostisch.
Der Lauf liest die dort unter `decision_tree.datasets`
referenzierten bisherigen Baum-Ergebnisse: gleiche Originalfälle, expandierte
Vergleichslabels, kanonische Stringwerte und Lexikonmerkmale. Nur das Embedding
wird ersetzt. Keine neue Übersetzung, keine Änderung der produktiven Pipeline.
Die Modellnamen `jina_de` und `e5_base` sind außerdem normale Methoden im
JSON-Baukasten; ihre festen Ketten normalisieren und trennen Identifier.
Der gezielte Baumvergleich übernimmt zusätzlich die bisherige Nr.-Expansion
aus der produktiven `multilingual_expanded`-Vorverarbeitung.

Alle Modelle laufen sequenziell auf CPU mit normierten Embeddings und Cosinus.
E5 erhält gemäß Modellkarte auf beiden Seiten `query: `; Jina verwendet Mean
Pooling über Sentence Transformers. Gewichte und separate Jina-Architektur
sind auf HF-Commits festgelegt. Downloads erfolgen nur beim ersten Laden in
den bestehenden HF-Cache; Docker lädt keine zusätzlichen Modelle.
Nach dem Download kann der Befehl mit `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1`
offline laufen. Vorhandene Ergebnisse werden nicht überschrieben:
`--output results/neuer-vergleich.json.gz` wählt eine neue Datei.

Das JSON speichert Rohmatrizen, Baumentscheidungen mit Gründen, Quellenhashes,
Modellrevisionen, Paketversionen, Laufzeiten und Precision/Recall/F1 pro Threshold.
Top-1 wird ausschließlich aus Rohscores berechnet; Gleichstand: erster Kandidat
wie in der bestehenden Auswertung. Labor: geänderte Schülerlabels gegen alle
Referenzkandidaten, Kontrolle/Zielfälle: bisherige vollständige Eingabemengen.
Modellladezeit, Embeddingberechnung und Gesamtlaufzeit werden getrennt gespeichert;
die Modelle nutzen jeweils einen Cache für eindeutige Labels über alle Fälle.

Ergebnisse vom 26.11.2026, Baum mit direkten Lexika (de=OdeNet, en=WordNet):

| Modell / Embeddingthreshold | Labor TP / FP / FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| MiniLM / 0,80 | 178 / 128 / 14 | 0,5817 | 0,9271 | 0,7149 |
| MiniLM / 0,85 | 177 / 68 / 15 | 0,7224 | 0,9219 | 0,8101 |
| MiniLM / 0,90 | 151 / 35 / 41 | 0,8118 | 0,7865 | 0,7989 |
| Jina / 0,80 | 160 / 1 / 32 | 0,9938 | 0,8333 | 0,9065 |
| Jina / 0,85 | 159 / 0 / 33 | 1,0000 | 0,8281 | 0,9060 |
| Jina / 0,90 | 146 / 0 / 46 | 1,0000 | 0,7604 | 0,8639 |
| E5 / 0,80 | 192 / 2430 / 0 | 0,0732 | 1,0000 | 0,1365 |
| E5 / 0,85 | 191 / 948 / 1 | 0,1677 | 0,9948 | 0,2870 |
| E5 / 0,90 | 170 / 220 / 22 | 0,4359 | 0,8854 | 0,5842 |

Top-1 der Rohscores im Labor: MiniLM 0,7647, Jina 0,8824, E5 0,8088.
E5 hat bei 0,85 allein 952 falsche Laborpaarvorkommen; sein hoher Scorebereich
verlangt andere Schwellen. Die Tabelle zeigt diagnostische Rasterpunkte, keine
validierte Modellauswahl. Jina gewinnt Präzision, verliert gegenüber dem bisherigen
Baum aber bei 0,75 sieben richtige Laborpaarvorkommen; nicht verlustfrei.
Kontrolle bei 0,80: MiniLM F1 0,7654, Jina 0,8750, E5 0,5089.
Unabhängige Aufgaben zur Bestätigung und Schwellenvalidierung fehlen weiterhin.

Finaler Offline-Lauf: `results/embedding-model-comparison-verified.json.gz`.
Das bestehende Outputschema und die Standardmethode bleiben erhalten.

Modellkonventionen und Lizenzen:
[Jina DE/EN (Apache-2.0)](https://huggingface.co/jinaai/jina-embeddings-v2-base-de),
[E5 Base (MIT; query-Präfix, hoher Cosinusbereich)](https://huggingface.co/intfloat/multilingual-e5-base).

### Gezielte Path-/Wu-Palmer-Ablation mit Jina

```sh
PYTHONPATH=src .venv/bin/python -m research.compare_taxonomy
```

`taxonomy_comparison` in `research/experiments.json` legt Quelle, Modell,
Embeddingthresholds 0,80/0,85/0,90 und Taxonomiegrenzen Path 0,25 / Wu-Palmer
0,80 fest. Der Lauf verwendet gespeicherte Jina-Scores und Lexikonmerkmale,
lädt keine Modelle und prüft alle Baselineentscheidungen inklusive Gründen exakt.
Vorhandene Dateien bleiben erhalten; `--output` wählt einen neuen Dateinamen.

Varianten: unveränderter Baum, nur Path, nur Wu-Palmer, beide. Jeder Filter wird
einmal mit der bisherigen Ein-Synset-Beschränkung (`single`) und einmal für alle
bekannten, verbundenen Paare (`covered`) geprüft. Nur Embeddingbestätigungen
können bei unterschrittener Grenze auf offen wechseln. Fehlende Abdeckung oder
Verbindung bleibt neutral. Gemeinsames Synset, Gegenrelationen und Stringstufen
bleiben unverändert. Mehrdeutige Maximalwerte sind keine Disambiguierung;
Path und Wu-Palmer können von unterschiedlichen Synsetpaaren stammen.

Ergebnis vom 26.11.2026: In allen 126 Kombinationen aus Datensatz, Lexikonquelle,
Embeddingthreshold und Variante bleiben TP/FP/FN identisch. Auch ohne
Ein-Synset-Beschränkung keine Verbesserung bei den getesteten Taxonomiegrenzen.
Labor mit direkten Lexika, alle Varianten:

| Threshold | TP | FP | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|
| 0,80 | 160 | 1 | 0,9938 | 0,8333 | 0,9065 |
| 0,85 | 159 | 0 | 1,0000 | 0,8281 | 0,9060 |
| 0,90 | 146 | 0 | 1,0000 | 0,7604 | 0,8639 |

Direkte Lexika haben für 23/192 richtige und 11/3264 falsche Laborpaarvorkommen
verfügbare Taxonomie. Bei 0,80 haben jedoch 0/48 richtige und 0/1 falsche
Embeddingbestätigungen verfügbare Taxonomie. Andere Regeln entscheiden die
abgedeckten Paare bereits vorher. Übersetztes WordNet deckt mehr Paare ab
(41/192 richtige, 499/3264 falsche), aber ebenfalls 0/40 richtige
Embeddingbestätigungen. Die eine falsche Embeddingbestätigung
`Vorname ↔ Familienname` hat Path 0,3333 und Wu-Palmer 0,8571 und passiert beide
Grenzen. Direkter OdeNet-Pfad: beide Begriffe bekannt, keine Taxonomieverbindung.

Über alle abgedeckten Laborpaare unterscheidet sich die Verteilung: WordNet-Median
Path richtig/falsch 1,0/0,1429, Wu-Palmer 1,0/0,5556. Diese Statistik wird bei
richtigen Paaren stark durch gemeinsame Synsets geprägt, ist keine zusätzliche
Synonymieevidenz. Falsche Paare können ebenfalls Werte bis 1 erreichen.
Kontrollfehler `Kunde bezahlt Lieferant ↔ Lieferant bezahlt Kunde` bleibt ohne
Ganzlabel-Lexikoneinträge ebenfalls außerhalb dieser Filter.

Artefakt `results/jina-taxonomy-comparison.json.gz`: Verteilungen nach Goldlabel,
TP/FP und Embeddinggrund; Abdeckung, Einzelpaare, Vorhersagen/Gründe, Precision,
Recall, F1, verlorene TP/entfernte FP, Auswertungszeit und Quellenhashes.
Keine Änderungen am produktiven Service oder den Standardentscheidungen.

### Aktuelle Lexikonwahl: ausschließlich OdeNet

`decision_tree.lexicons` verwendet jetzt `["odenet"]`. Alle Labels werden ohne
Sprachauswahl und ohne Übersetzung in OdeNet 1.4 nachgeschlagen. Die interne
Quellenkennung `de` dient nur der Auswahl von OdeNet und ist keine Spracherkennung;
Originalelemente bleiben erhalten. Fehlende Einträge bleiben unbekannt und
werden nicht als fachlich falsch bewertet. String-/Embeddingstufen bleiben erhalten.
WordNet (`wordnet`) und die bisherige sprachabhängige Variante (`native`) bleiben
optional auswählbar, sind im aktuellen Baum aber deaktiviert. Dies betrifft den
Forschungsbaum, nicht den produktiven Service und nicht historische Experimente.

Die fünf realen Laborfälle sind nicht ausschließlich deutsch: Vier Varianten
sind deutsch, `laboratory-languages` enthält 19 englisch annotierte Schülerlabels
(z.B. Building, Room number, Experiment) und weitere deutsche Labels. Der
englische Fall bleibt im Vergleich enthalten; Jina vergleicht weiterhin DE/EN.
Die reine OdeNet-Abfrage benötigt kein `language`-Attribut. Die vorhandene
DE-spezifische Abkürzungsexpansion verwendet in diesem Forschungsstand weiterhin
die Sprachangaben der Testdaten; das ist eine getrennte Vorverarbeitung.

Neue Ergebnisdateien: `results/decision-tree-odenet-only-*-20261126.json.gz`
und `results/embedding-model-comparison-odenet.json.gz`. Historische Vergleiche
mit WordNet bleiben erhalten; der Taxonomieversuch verweist ausdrücklich auf
seinen bisherigen, eingefrorenen Eingabestand.

Jina + ausschließlich OdeNet, geänderte Laborlabels inklusive englischer Variante:

| Embeddingthreshold | TP | FP | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|
| 0,80 | 161 | 1 | 0,9938 | 0,8385 | 0,9096 |
| 0,85 | 160 | 0 | 1,0000 | 0,8333 | 0,9091 |
| 0,90 | 151 | 0 | 1,0000 | 0,7865 | 0,8805 |

Kontrollfälle und gezielte Fälle bleiben bei diesen Schwellen gegenüber dem
bisherigen direkten Lexikonpfad unverändert. Bekannte Entwicklungsdaten.
