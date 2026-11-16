# analytical-feedback

Serviceversion `2.2.1`, Image `v10`, Ausgabe `analysis-feedback/v3` in
`workflow-result/v1`. Der Dienst projiziert ausschließlich Matcher-Fakten und
berechnet die verbindliche `recognition`-Übersicht. Er entscheidet keine
Zuordnungen oder Eigenschaften erneut.

Verbindungsbeschriftungen ohne eigene Identitätsprüfung bleiben Annotationen und
gehören nicht in den Erkennungsnenner. Historische Kategorieverträge bleiben lesbar.

Erkannt sind ausgewählte 1:1-Paare mit `identity.status = uniquely_supported`,
hinreichendem Identitätsanker und nicht zirkulären Abhängigkeiten. `supported`,
`unresolved` und `not_evaluated` zählen nicht. Typkompatibilität allein genügt
nicht. Abweichungen bei Namen, Typ, Besitzer, Kindern oder Verbindungen bleiben
getrennte Fakten und heben eine belegte Identität nicht automatisch auf.

## Aktueller Vertrag

[output.schema.json](schemas/output.schema.json) beschreibt aktuelle und gespeicherte
Altanalysen sowie unter `$defs.feedbackReportV3` den Feedbackbericht.
Python-Validator und TypeScript-Adapter prüfen Status, Original-IDs, Anzeigeziele,
Zähler und Herkunft. Die Dienstgrenze prüft Snapshot, Graph-, Inventar-, Kandidaten-,
Vergleichs- und Analysehashes.

- `recognition`: `basis: uniquely_supported`, dynamische `buckets`, `overall` und
  `unmatchedSubmission`. Jede Zählzeile enthält `recognized`, `expected`,
  `percent`, `evaluationStatus`. Formel: `recognized / expected * 100`.
  Leere Gruppen/Typen erscheinen nicht; eine leere Gesamtmenge hat
  `not_applicable`, nicht auswertbare Zeilen `not_evaluated`, jeweils mit `percent: null`. Teilweise auswertbare Kategorien heißen `partial`
  und behalten den vollständigen Referenznenner; sonst `evaluated`.
- `annotations`: genau ein Eintrag pro Abgabeobjekt mit Original-ID und Objektart
  in `target`, optionalem `referenceId`, `mappingReason` und
  Abhängigkeiten, kompaktem Identitätsprofil, Fakten und Hinweisen.
- `identity`: Status und relevante Kriterien. Eigenschaftsfakten verwenden separat
  `satisfied`, `violated`, `unresolved`, `not_evaluated`, `not_applicable`.
  Es gibt keine zusätzlichen Annotation-Gesamtstatus, `checks` oder `consistency`.
- `facts`: stabile Fakt-ID, Code, Status, Referenz-/Abgabe-IDs und Beweisgrundlage.
  Doppelte Objektbeschreibungen und Identitätskriterien werden entfernt.
  Kinderfakten behalten korrekt enthaltene, verschobene, offene und nachweislich
  fehlende Kinder. Positive Einzelfakten bleiben auch bei Abweichungen erhalten.
- `hints`: Code, Fakt-ID, Geltungsbereich und explizite Original-ID-Ziele.
  `findingId` bündelt denselben Positionsbefund.
- `referenceHints`: nicht zugeordnete Referenzobjekte mit Beweisen und Anzeigeziel
  am erkannten Parent/Endpunkt oder am Modell. Unmatched bedeutet nicht automatisch
  nachgewiesen fehlend.
- `connectionGroups` und `groupIds`: Gruppenfakten separat von individuellen
  Verbindungsfakten. Ein Gruppendefizit identifiziert keine einzelne fehlende Kante.
- `structuralContainers`: separate Objektzahlen; Hilfscontainer gehören nicht
  in fachliche Erkennungsnenner.

Die Zeilen entstehen ausschliesslich aus den Objekten der jeweiligen Musterloesung:
eindeutige bestehende Vergleichsgruppen werden zusammengefasst, nicht gruppierte
Typen separat gezaehlt. Gruppenkennungen sind nach Sprache, Version und Objektart
getrennt. Eine Zeile enthaelt `id`, `label`, `kind`, `grouped` sowie die vier
Zaehlerfelder. Jeder Referenzgegenstand zaehlt genau einmal. Ueberlappende Gruppen
bleiben entsprechend dem Parser als nicht eindeutig gruppierter Typ separat;
es wird keine transitive Gruppierung eingefuehrt. Nur in der Abgabe vorkommende
Typen erzeugen keine Referenzzeile. Nicht zugeordnete Abgabeobjekte bleiben separat.
Strukturelle Hilfscontainer werden weiter ausgeschlossen. Zusaetzliche
`elementCategories`-Deklarationen, neue Sprach-Releases oder Migrationen sind
fuer diese Erkennungsuebersicht nicht erforderlich.
Die Erkennungsquote ist keine Korrektheitsquote und keine Note.

## Veröffentlichung und Kompatibilität

Der Dienst speichert `analysis/<referenceKey>/<analysisKey>.json` und schreibt
das vollständige kompakte Envelope als eine JSON-Zeile auf stdout. Dagu bewahrt
`analysis-result.json` auf und reicht `analysisPath` an Feedback Generation weiter.
Pfad, Schlüssel, Hash, Auswertung und Referenzpaar müssen zusammenpassen.

`analysis-feedback/v1` mit keiner Revision oder `contractVersion` 1.1, 1.2 und 1.3
bleibt in API, Python-Leser und Frontend lesbar. Diese historischen Zahlen werden
nicht nachträglich als aktuelle Erkennung umgedeutet.
`analysis-feedback/v2` bleibt ebenfalls lesbar; seine feste Kategorieuebersicht
bleibt eine historische Ausgabe. Neue Ausgaben verwenden ausschliesslich v3.
Die alte Analyseerzeugung aus Vergleichen ohne Identitätsfakten wurde entfernt.
Für neue v2-Berichte ist eine Neuberechnung aus aktuellen Matcher-Fakten nötig;
gespeicherte Artefakte und unveränderliche Sprach-Releases werden nicht umgeschrieben.


Die API gibt Detailanalysen und Diagnoseartefakte weiterhin nur Moderatoren und
Administratoren aus. Studierende erhalten die veröffentlichte Erkennungsübersicht
und eigene nicht zugeordnete IDs, keine Referenznamen, Referenzfakten oder Rohlogs.
Die UI zeigt Übersicht und Details für dasselbe Referenzpaar, positive Fakten,
Abweichungen und offene Prüfungen gleichzeitig; ausführliche Diagnosen sind optional.

Prüfergebnisse und Größenvergleich: [Cleanup-Nachweis](CLEANUP.md).

## Lokale Regression

```powershell
python -B -m unittest discover -s dagu/workflow-services/analytical-feedback/tests -q
```

Schema und tatsächlicher Frontendadapter verwenden installiertes TypeScript/AJV
aus `web/node_modules`. Ohne diese Werkzeuge wird die Adapterprüfung explizit
übersprungen. Modellfixtures verwenden generische kompatible Kandidaten ohne
Embeddingberechnung, Synonymdienst oder historische eingefrorene Kandidatenketten.
