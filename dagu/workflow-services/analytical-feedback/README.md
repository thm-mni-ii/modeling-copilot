# analytical-feedback

Der Dienst fasst einen vorhandenen Graphvergleich elementbezogen zusammen; er
trifft keine neuen Zuordnungen. Er validiert Snapshot, Graphen, Inventare,
Kandidaten, Vergleich und deren Hashketten. Eingabeauswahl und Ergebnisvertrag
stehen in `schemas/input.schema.json` und `schemas/output.schema.json`.

Die Ausgabe liegt als `workflow-result/v1` mit einem `analysis-feedback/v1`
unter `analysis/<referenceKey>/<analysisKey>.json` im Evaluation-Workspace.
Der inhaltsbasierte Schlüssel und `analysisHash` sichern eine unveränderliche,
bei identischem Inhalt wiederholbare Veröffentlichung.

`annotations` enthält höchstens einen Eintrag je Abgabeobjekt mit Original-ID,
vorläufigem Gegenstück, Entscheidungsregel, notwendigen Abhängigkeiten,
Prüfstatus und kurzen Hinweisen. Lokale Zähler unterscheiden erwartete,
erkannte und ungeklärte Kinder und Verbindungen. `referenceHints` adressiert
ungeklärte Referenzobjekte nach Möglichkeit am erkannten Parent oder Endpunkt,
ansonsten am Modell. `summary` enthält referenzbezogene Erkennungszahlen.
Der Kontext eines strukturellen Zwischencontainers ist ausdrücklich abgeleitet
und keine neue Zuordnung.

Alle Zuordnungen bleiben `provisional`. Eine Typabweichung innerhalb einer
Vergleichsgruppe ist keine automatische fachliche Fehlermeldung. Offene Elemente
oder Verbindungen gelten nicht als bestätigt fehlend oder zusätzlich;
Verbindungsgruppen begründen keine individuelle Verbindungsidentität.
Kandidatenmatrizen, Entscheidungsereignisse und vollständige Graphen verbleiben
in ihren ursprünglichen Workflow-Artefakten.

Der Dienst gibt das kompakte Envelope vorerst auf stdout aus. Dagu speichert es
als `analysis-result.json` und übergibt den Workspace-Pfad an
`feedback-generation`. Für die Übergabe akzeptiert der Workflow sowohl
`analysisPath` im Envelope als auch `path` in einer kompakten Statusausgabe;
ein fehlender oder ungültiger Pfad lässt den Übergabeschritt fehlschlagen.
Die API gibt die Analyse nur an Moderatoren und
Administratoren aus; die bestehende Besitzerprüfung der Auswertung gilt weiter.
