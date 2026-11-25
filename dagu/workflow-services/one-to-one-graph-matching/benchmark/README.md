# Graph-Matching-Benchmark

Testabgaben mit bekannter Zuordnung, erzeugt aus den gespeicherten Musterlösungen. Jede Abgabe
behält die Zellen-IDs der Referenz; das wahre Gegenstück eines Referenzobjekts ist also das
Abgabeobjekt mit derselben ID. Der Benchmark läuft gegen die ausgerollten Workflow-Dienste und
prüft damit die echte Kette aus Parser, Inventar, Synonym Matching, Graphvergleich, Analyse und
Feedback.

## Referenzen

| Schlüssel | Sprache | Herkunft |
|---|---|---|
| `uml-order-management` | UML-Klassendiagramm, englische Beschriftungen | Musterlösung „Order Management“ |
| `serm-laboratory` | SERM, deutsch | Musterlösung „Laborverwaltung“ |
| `serm-game-studio` | SERM, deutsch | Musterlösung „Entwicklerstudio“ |
| `erm-laboratory` | ERM, deutsch | Laborverwaltung, von `generate.py` nach ERM übertragen: Entitäten und Beziehungen bleiben, Attribute werden Ellipsen mit Attributkante |

`references/` enthält Musterlösungen, Sprachversionen und für ERM nur Zellstile ohne Beschriftung.

## Prozess- und weitere Diagrammarten

`process_probe.py` ergänzt Fälle für Sprachen, die die Plattform noch nicht hat: BPMN, EPK und
UML-Aktivitätsdiagramm als minimale Benchmark-Sprachdefinitionen (`benchmark-*`, nur Element- und
Verbindungstypen, Kantenbeschriftungen und Vergleichsgruppen). Dazu kommen zwei Fälle mit der echten
UML-Klassensprache: gleiche Attributnamen in mehreren Klassen und Attribute im Format `+ name: Type`.
Ein Bestellprozess wird je Sprache abgebildet. Die Varianten sind:

- Verb-Objekt-Umstellung, Nominalisierung und umformulierte Ereignisse
- Übersetzung und geänderte Bedingungen
- vertauschte Reihenfolge, anderer Gatewaytyp und implizite Parallelität
- andere Lane und halber Prozess

```powershell
python dagu/workflow-services/one-to-one-graph-matching/benchmark/process_probe.py --out .local/tmp/probe/cases --languages .local/tmp/probe/languages.json
```

Danach wie unten mit `run.py` (dabei `languages.json` aus dem Probe-Lauf verwenden) und `evaluate.py`.

## Testfälle

| Fall | Inhalt |
|---|---|
| `identical` | unveränderte Musterlösung |
| `notation` | alle Beschriftungen in anderer Schreibweise (Groß/klein, Bindestrich, Unterstrich, Punkt) |
| `typo` | 40 % der Beschriftungen mit einem fehlenden Buchstaben in der Wortmitte |
| `abbreviation` | Kürzel ausgeschrieben oder gekürzt: `Nr.` → `nummer`, `Number` → `No`, `Bezeichnung` → `Bez.` |
| `synonym` | alle Beschriftungen durch ein Synonym aus `lexicon.json` ersetzt |
| `translation` | alle Beschriftungen übersetzt (deutsch ↔ englisch) |
| `short_form` | Kurzform oder Wortteil (`Forschungsprojekt` → `Projekt`) |
| `wrong_label` | 30 % der Objekte und Attribute mit fachfremdem Begriff; Gegenstück nur strukturell |
| `shuffled_labels` | Beschriftungen der Hauptobjekte zyklisch verschoben |
| `distractors` | je Hauptobjekt ein zusätzliches Köderattribut (`<Attribut> 2`) |
| `moved_attributes` | 30 % der Attribute unter einem anderen Besitzer |
| `subset_small`, `subset_medium`, `subset_large` | 25 %, 50 %, 85 % der Hauptobjekte samt Kindern |
| `subset_medium_synonym` | 50 % der Hauptobjekte, alle verbliebenen Beschriftungen als Synonym |
| `realistic_mix` | 85 % der Objekte, zwei Tippfehler, zwei Synonyme, ein Kürzel, ein falscher Begriff, ein verschobenes Attribut, ein Köder |
| `foreign_solution` | Musterlösung einer anderen Aufgabe als Abgabe |

Soll je Referenzobjekt: zuordenbar bei `exact`, `notation`, `typo`, `abbreviation`, `synonym`,
`translation`, `short_form`, `moved`. Bei `removed` gibt es kein Gegenstück, bei `wrong_label` und
`shuffled` nur ein strukturelles.

## Ablauf

```powershell
python dagu/workflow-services/one-to-one-graph-matching/benchmark/generate.py --out .local/tmp/benchmark/cases
```

Danach `cases/`, `run.py` und `references/languages.json` in den Workflow-Data-Pod kopieren und dort
`python run.py CASES LANGUAGES OUT` starten. Der Runner ruft die Dienste über
`http://workflow-services:<port>/run` in derselben Reihenfolge wie der DAG auf, verwendet je Fall
einen temporären Arbeitsordner `replay-<uuid>-<n>` und löscht ihn danach. Die Ergebnisse
zurückkopieren und auswerten:

```powershell
python dagu/workflow-services/one-to-one-graph-matching/benchmark/evaluate.py .local/tmp/benchmark/cases .local/tmp/benchmark/out --markdown report.md
```

`evaluate.py` ordnet jedes Referenzobjekt ein: `certain` (eindeutig mit dem wahren Gegenstück),
`hint`, `partial`, `missed`, `wrong` (eindeutig mit einem anderen Objekt), `structural` (bei falscher
Beschriftung über die Struktur gefunden) oder `absent_ok`. Dazu kommen die Textwerte der Sollpaare
je Stufe, damit sich Text- von Strukturursachen trennen lassen.

## Regression

- `run.py … --keep` speichert die Arbeitsordner (Graphen, Inventare, Kandidaten).
- `local_run.py ERGEBNISSE AUS` rechnet Matcher, Analyse und Feedback aus dem Repo-Stand lokal auf denselben Eingaben nach. Mit `--matcher SRC` läuft ein anderer Matcherstand, etwa aus dem Pod kopiert, zur Prüfung des Werkzeugs.
- `evaluate.py … --summary S.json` schreibt je Fall und Objekt Ergebnis und Gegenstück.
- `compare.py ALT.json NEU.json` meldet gewonnene, verlorene und neue falsche Paare. Der Exitcode 1 bedeutet: Treffer verloren oder neue falsche Zuordnung.

Grundlinie ist `results/baseline-2.12.0.summary.json`. Ein lokaler Nachlauf des Pod-Codes 2.12.0 ergab gegenüber dem Clusterlauf keinen Unterschied.

## Grenzen

- Lexikon, Soll und ERM-Übertragung stammen aus einer einzigen, von Claude erstellten Quelle.
- Bei zwei gleich beschrifteten Geschwistern unter einem Besitzer ist die ID-Zuordnung nicht
  entscheidbar; `wrong` kann dort ein Artefakt des Solls sein.
- `foreign_solution` hält jede Zuordnung für falsch, auch wenn beide Aufgaben denselben Begriff
  enthalten (`PersonalNr.`, `E-Mail`).
- Die Benchmark-Sprachen für BPMN, EPK und Aktivitätsdiagramm sind Testgerüste, keine Plattformsprachen.
- Die Ergebnisse vom 24.11.2026 gegen Matcher `2.12.0` stehen in `results/`.
