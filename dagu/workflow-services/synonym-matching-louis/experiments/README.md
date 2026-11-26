# Erweiterbarer Forschungsbaukasten

Hier liegen **alle bisherigen Verfahren, Kombinationen, Preprocessing-Varianten,
Datensätze, Schemas und Tests**. Das ist ausführbarer Forschungscode, kein
stillgelegtes Archiv. Der ausgewählte neue Servicekern bleibt unter `../src/`.

## Starten

Alle folgenden Befehle aus dem Louis-Wurzelordner, mit derselben aktivierten venv:

```sh
pip install -r experiments/requirements-research.txt
python scripts/run_experiments.py compare --output results/alle-experimente.json
python scripts/run_experiments.py tests -q
```

Die zusätzlichen Forschungsabhängigkeiten betreffen beispielsweise spaCy,
Übersetzung und statische Wortvektoren. Sie sind nicht im neuen Standalone-Image.
Für Lemma-/Nomen-Experimente zusätzlich die bisherigen spaCy-Modelle vorbereiten:

```sh
python -m spacy download de_core_news_sm
python -m spacy download en_core_web_sm
```

Einzelne Verfahren auswählen, ohne alle Modelle zu laden:

```sh
python scripts/run_experiments.py compare \
  --only 'normalize+lowercase → levenshtein' \
  --output results/string-probe.json
```

Weitere vorhandene Befehle, mit ihren bisherigen Argumenten:

```sh
python scripts/run_experiments.py compare --help
python scripts/run_experiments.py compare_lingua --help
python scripts/run_experiments.py compare_embeddings --help
python scripts/run_experiments.py compare_taxonomy --help
python scripts/run_experiments.py build_laboratory_cases
python scripts/run_experiments.py rank_results --input results/string-probe.json
python scripts/run_experiments.py cli --input examples/input.json
```

Auch Komponenten-, Gewichtungs- und Sprachpfadvergleiche sind über ihre Modulnamen
aufrufbar. Manche dieser gezielten Replays benötigen wie bisher gespeicherte
Zwischenergebnisse. Der allgemeine `compare`-Baukasten berechnet frische Scores.
Neue Outputnamen verwenden; bestehende Ergebnisse werden nicht überschrieben.

## Wo erweitern?

| Aufgabe | Datei relativ zu `experiments/` |
|---|---|
| Konfigurationen, Ketten, Gewichtungen, Kombinationen | `research/experiments.json` |
| Neues Einzelverfahren | `src/synonym_matching/methods.py` |
| Neue Vorverarbeitung | `src/synonym_matching/preprocessing.py` |
| Neue Fusion | `src/synonym_matching/combinations.py` |
| Daten und Sollzuordnungen | `research/*-cases.json` |
| Zugehörige Regressionen | `tests/` |

Der Starter führt den bisherigen Code in einem separaten Prozess aus. Damit
kollidieren alte und neue gleichnamige Python-Pakete nicht. Relative Argumente
werden ab `experiments/` aufgelöst: `research/experiments.json` bezeichnet also
den bisherigen großen Baukasten, nicht die neue kompakte Konfiguration.

`.cache` und `results` werden bei Bedarf als lokale Links auf `../.cache` und
`../results` angelegt; keine Modellduplikate. Der HF-Cache folgt wie bisher
`HF_HOME` bzw. dem Hugging-Face-Standard. Diese Links werden nicht eingecheckt.
Fehlende Wortvektoren/Lexika werden weiterhin als fehlende Ressourcen behandelt;
der Starter lädt nichts automatisch herunter.

Vorbereitung zusätzlicher früherer Ressourcen:

```sh
python scripts/run_experiments.py download_models
python scripts/run_experiments.py download_lexicons
python scripts/run_experiments.py download_lexicons --odenet
```

Opt-in-Tests mit echten, zuvor vorbereiteten lokalen Modellen:

```sh
RUN_MODEL_TESTS=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  python scripts/run_experiments.py tests -m integration -q
```

Der gesamte bisherige Kern und seine 285 normalen Tests bleiben erhalten.
Lange historische Ergebnisberichte stehen in `HISTORY.md`, nicht in der kurzen
Haupt-README. Die damalige Prototyp-CLI und ihr Combined-Score-Schema bleiben
erhalten; sie sind **nicht** der Vertrag des produktiven Workflow-Services.
