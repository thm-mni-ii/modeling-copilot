# feedback-generation

Serviceversion `2.2.0`, Image `v9`, Ausgabe `feedback-report/v3` in
`workflow-result/v1`.

Der Dienst verlangt `WORKFLOW_EVALUATION_ID`, `REFERENCE_KEY` und
`ANALYSIS_INPUT_PATH`. Er validiert das konkrete Analyseartefakt gegen Snapshot,
Referenzpaar, Vergleich, Pfad und Hash. Anschließend übernimmt er dessen
`recognition` unverändert und ergänzt Analyse-/Vergleichsprovenienz und
`feedbackHash`. Es gibt keine eigene Aggregation aus vorläufigen Matcher-Metriken.

`recognition` enthält dynamische Gruppen-/Typzeilen, Gesamtzahlen und separat nicht zugeordnete
Abgabeobjekte. Details und Statusdefinitionen stehen im
[Analysevertrag](../analytical-feedback/README.md); das gemeinsame
[JSON-Schema](../analytical-feedback/schemas/output.schema.json) definiert
`$defs.feedbackReportV3`. Die UI zeigt diese veröffentlichten Werte an, ohne aus
Zuordnungen neue Erkennungszahlen zu berechnen. Die Quote ist keine
Korrektheitsquote und keine Note; `assessmentAvailable` bleibt `false`.

Die vollständige kompakte Ausgabe bleibt eine JSON-Zeile auf stdout und wird von
Dagu als `feedback-result.json` gespeichert. Alte Felder `categories`, `totals`,
`analyticalSummary` und redundante Strukturkopien sind in v2 entfernt und bleiben in v3 entfernt.

Gespeicherte v1-/v2-Artefakte bleiben unverändert als historische technische Ergebnisse
verfügbar. Sie werden nicht als aktuelle `recognition` angezeigt. Neue Berichte
aus alten Analysen oder ohne Analysepfad erfordern eine Neuberechnung; der bisherige
parallele Generierungspfad ohne Analyse ist entfernt.
