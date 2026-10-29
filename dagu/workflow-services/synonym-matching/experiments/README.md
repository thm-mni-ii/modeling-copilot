# Experimentprotokoll

## Daten und Grenzen

`data/synthetic.json`: 18 synthetische Aufgaben mit je 3 Referenz- und 3
studentischen Elementen, 162 vollständig annotierte Paare. 10/4/4 Aufgaben in
Training/Validierung/Test. Die Annotationen sind Vorschläge für technische Tests,
**nicht unabhängig fachlich validiert**. Kein Export realer studentischer Modelle
ist enthalten. Die kleine Stichprobe erlaubt keine belastbare Qualitätsrangliste.

Reale Daten sind gemäß Issue #19 zusätzlich nötig. Ein Importdatensatz hat
`version: 1`, `provenance`, `tasks`; jede Aufgabe:

- `id`: eindeutige Aufgaben-/Kandidatensatzkennung;
- `group`: gemeinsame Ursprungsaufgabe für alle Abgaben und Ableitungen;
- `families`: Begriffsfamilien einschließlich Übersetzungen/Tippfehlervarianten;
- `split`: `train`, `validation` oder `test`;
- `category`: Falltyp;
- `reference`, `student`: geordnete Elementlisten;
- `annotations`: vollständige Referenz×Student-Matrix aus `correct`, `possible`,
  `incorrect`.

Unannotierte Paare dürfen **nicht** still als Negative ergänzt werden. Die
Kategorie ist pro synthetischem Kandidatensatz vergeben; für eine feingranulare
Analyse realer Daten sollten Kandidatensätze passend kuratiert werden.
Reale Exporte und Lernerdaten nicht in Git übernehmen.

## Leakage und Auswahl

Gruppen und deklarierte Begriffsfamilien dürfen keine Splitgrenze überschreiten.
Auch wiederholte/vertauschte normalisierte Textpaare über Splitgrenzen werden
abgelehnt. Die Prüfung kann semantische Verwandtschaft nicht selbst erkennen:
Die Familienzuordnung muss vorab fachlich geprüft werden. Synthetische Varianten
immer der Ursprungsgruppe zuordnen, nicht nachträglich zufällig verteilen.

Das Schema ist bewusst strenger als ein reiner Aufgaben-Split. Für eine spätere
separate Studie zu bekannten Begriffen in neuen Aufgaben den Splitvertrag bewusst
versionieren, nicht die Leakage-Prüfung still umgehen.

Basisverfahren verwenden eingefrorene Encoder und feste String-Metriken. Logistic
Regression und Random Forest lernen ausschließlich auf eindeutigen Trainingspaaren.
`possible` wird nicht in ein willkürliches Trainingslabel umgewandelt. Es werden
keine Encoder trainiert. Wenn künftig Basisverfahren trainiert werden, sind
gegruppenweise Out-of-Fold-Trainingsfeatures notwendig.

Hyperparameter sind vorab fest: Logistic Regression C=1, balanced, max_iter=1000;
Random Forest 100 Bäume, max_depth=4, min_samples_leaf=2, balanced, n_jobs=1.
Seed aus der Variantenkonfiguration. Kein implizites Hyperparameter-Tuning.
Threshold pro Methode/Variante: bestes Validierungs-F1, bei Gleichstand höhere
Precision, dann höherer Threshold. Das Raster steht in der Suite. Test wird nur
mit diesen Thresholds berichtet. Nach Sichtung des Tests keine neue Variante
auf demselben Test als unabhängig bestätigt ausgeben.

## Vergleichsblöcke

`baselines.json`: Rohtexte, minimale Normalisierung, Lowercasing und Identifier-
Trennung. Jeweils fünf Einzelmetriken, Mean, Max, Weighted Mean, Logistic
Regression, Random Forest. Alle Kombinationen verwenden bereits berechnete
Features, nicht erneut encodierte Paare.

`full.json`: zusätzlich direkter multilingualer Encoder und DE→EN→englischer
Encoder, String-/Embedding-Ablationen und mehrere Hybridgewichte. Modell- und
spaCy-Abhängigkeiten müssen installiert sein. Ein Fehler wird als fehlgeschlagene
Variante gespeichert, nicht als schlechtes Qualitätsergebnis oder Zero-Score.

SVM, automatische Spracherkennung, WordNet und regelbasierte Kombinationen sind
nicht Bestandteil dieses ersten Stands. Die Schnittstellen erlauben Erweiterungen,
ohne Benchmark- und CLI-Vertrag neu zu schreiben.

## Metriken

- Precision/Recall/F1, TP/FP/FN/TN: nur eindeutige Paare in der Hauptauswertung.
  Undefined Precision/Recall bei null Vorhersagen/Positiven wird als 0 behandelt.
- `macro_task_f1`: ungewichteter Mittelwert pro Aufgabe; zusätzlich globale Werte.
- `top1_accuracy`: pro Referenz mit mindestens einem korrekten Kandidaten;
  vollständige Kandidatenmenge, unabhängig vom Threshold. Mehrere korrekte
  Kandidaten sind zulässig. Eingabereihenfolge entscheidet bei Score-Gleichstand;
  die Anzahl betroffener Queries wird separat angegeben.
- `query_coverage`: Anteil der Referenzen mit mindestens einem Treffer oberhalb
  des Thresholds. `no_match_rejection`: korrekte Ablehnung bei ausschließlich
  falschen Kandidaten. Referenzen mit nur `possible` und negativen Kandidaten
  werden nicht als sichere No-Match-Fälle behandelt.
- `mean_top1_top2_margin`: deskriptive Mehrdeutigkeit im Kandidatenkontext;
  keine Sicherheitsschätzung und keine strukturelle Graphanalyse.
- `slices.csv`: nach Aufgabenkategorie, Sprachpaar und alternativer Behandlung von
  `possible` als positiv/negativ.
- Laufzeit: pro Methode, Preprocessing, Kombination und Gesamtzeit je Task in
  `matrices.json`; Modelllade-/Encoding-/Übersetzungszeiten zusätzlich kumulativ.
  `warm_timings.json` enthält Wiederholungen mit warmer Engine/Featurecache.
  Jede Variante startet mit einer neuen Engine und leerem Featurecache im RAM.
  Innerhalb einer Variante werden Features wiederverwendet (Hit/Miss-Zähler).
  Modell-Downloadzeit gesondert vom geladenen Betrieb betrachten.

## Gespeicherte Artefakte

Jeder neue Run speichert Dataset, Suite, Datenhash, Splitmanifest, Python-/Paket-
und Plattforminformationen, Git-Commit/Dirty-Status und Quellcodehashes. Pro
Variante vollständige Matrizen, transformierte Texte, Modellrevisionen,
Paarvorhersagen, ausgewählte Thresholds und Kombinatorparameter. Trainierte Modelle
bleiben nur während des Experiments im Speicher; kein eigener Modell-Export.
`summary.csv`, `validation_thresholds.csv`, `slices.csv`, `REPORT.md` bilden die
Vergleichsansichten. Laufzeiten sind maschinenabhängig und nicht exakt reproduzierbar;
Scores sind bei gleicher Umgebung innerhalb numerischer Toleranzen zu vergleichen.

Ergebnisse bleiben unter dem ignorierten `results/`. Für einen Forschungsbericht
gezielt freigegebene, datenschutzgerechte Zusammenfassungen versionieren.
Aktuell sind keine vollständigen Benchmark-Ergebnisse dokumentiert. Die lokale
Installation und beide Modellpfade sind inzwischen durch Tests verifiziert.

## Literatur als Experimentregister

Die Referenzen stehen in [Issue #19](https://github.com/thm-mni-ii/modeling-copilot/issues/19).
Folgende Zuordnungen sind Recherche-/Experimenthypothesen, keine behaupteten
Reproduktionen der Originalarbeiten:

| Ausgangspunkt | Zu prüfende Hypothese | Abbildung im Prototyp |
| --- | --- | --- |
| Jayal & Shepperd (2009), Problem of Labels in E-Assessment | Labelvarianten brauchen eine eigene Fehleranalyse | Übersetzung, Tippfehler, Abkürzungen, schwierige Negative |
| Kenter & de Rijke (2015), Short Text Similarity | Embedding-Scores ergänzen lexikalische Ähnlichkeit | String vs. Embedding vs. Hybrid |
| Lastra-Díaz et al. (2019), lineare Kombinationen | Einfache Kombinationen sind prüfenswerte Baselines | Mean/Weighted Mean |
| Martinez-Gil (2022), Stacking-Review | Lernkombination kann komplementäre Scores ausnutzen | Logistic Regression/Random Forest mit getrennten Gruppen |

Die Arbeiten vor wissenschaftlichen Aussagen im Original lesen und die genaue
Operationalisierung dokumentieren. Ein bekannter Titel oder Ergebnis auf einem
anderen Datensatz belegt keine Verbesserung für diese Modellbezeichnungen.
