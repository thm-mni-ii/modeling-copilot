# model-label-extraction

Sammelt pro Modell ein vollständiges Labelinventar als Grundlage späterer
Zuordnungskandidaten für die Graphüberdeckung.

- Aufnahme: `nodes[].label` von Elementen, Kind-Elementen und Verbindungsknoten
  sowie `edges[].label` bei `kind: connection`, einschließlich Rollenbeschriftungen.
- Original-ID und Text bleiben erhalten, auch bei Standardtexten, festen Labels,
  gleichen Bezeichnungen und mehrteiligen Texten; keine Zerlegung.
- Entfallen: leere bzw. reine Formatierungstexte und strukturelle Kanten.
  Feedback und technische Root-/Layer-Zellen entfernt bereits der Graph-Parser.

Synonym-Matching ist für frei benannte Elemente, Attribute, Beziehungen und Rollen
gedacht. Kennungen (`R1`), feste Notation, Kommentare und Werte (`10 kΩ`, `0..n`)
können als Labels im Inventar stehen; ihre Matching-Eignung wird hier noch nicht
klassifiziert. Keine Synonymzuordnung, Wertprüfung oder Einheitenumrechnung.
Separate `properties` sind keine Label-Einträge. `type`, `definition` und
`parentId` bleiben als Kontext im Graphen; `allowLabelEdit` bestimmt keine
Matching-Eignung und weist keine Nutzereingabe nach.

Eingabe: `workflow-result/v1` mit `result.graph` (Version 2) und `result.source`.
Ausgabe: `result.source` und `result.elements` (`id`, `label`) in `workflow-result/v1`;
Identität über `(source.key, id)`.
Dateiübergabe über `WORKFLOW_INPUT_PATH` / `WORKFLOW_OUTPUT_PATH` oder
`--input` / `--output`; Workflow-Ausgabe: `labels/<modelKey>.json`.
