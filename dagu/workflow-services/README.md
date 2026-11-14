# Workflow-Services für die Modellauswertung

`model-evaluation-graph-matching` verwendet sieben eigenständige Service-Images:

- `workflow-data` validiert und speichert den eingefrorenen Eingabesnapshot.
- `graph-parser` normalisiert die Modellgraphen.
- `model-label-extraction` extrahiert die Elementinventare.
- `synonym-matching` berechnet semantische Kandidaten.
- `one-to-one-graph-matching` erzeugt vorläufige Zuordnungen und Strukturprüfungen.
- `analytical-feedback` erstellt kompakte elementbezogene Hinweise.
- `feedback-generation` erzeugt die kompakte Feedbackprojektion.

Graph Matching verwendet Serviceversion `1.2.0` und Image `v3`, Analytical
Feedback `1.3.0` und Feedback Generation `1.0.3` mit Image-Tags `v6`.
Die übrigen Dienste bleiben bei `1.0.0` und `v1`.
Alle Artefaktverträge verwenden `/v1`; Matcher-Fakten tragen Version `1.1`,
Identitätsevidenzen `1.0`. Die Analyse ergänzt Vertragsrevision `1.3` und liest
frühere Revisionen weiter.
Die benötigten Modell- und Paarabläufe sind
intern in der einzigen Workflowdatei eingebettet.

Build und lokale Kubernetes-Bereitstellung sind in [dagu/README.md](../README.md)
beschrieben. Die übrigen Serviceordner enthalten frühere Vorlagen oder
Forschungsressourcen und werden vom Auswertungsworkflow nicht verwendet.
