# Workflow-Services für die Modellauswertung

`model-evaluation-graph-matching` verwendet sieben eigenständige Service-Images:

- `workflow-data` validiert und speichert den eingefrorenen Eingabesnapshot.
- `graph-parser` normalisiert die Modellgraphen.
- `model-label-extraction` extrahiert die Elementinventare.
- `synonym-matching` berechnet semantische Kandidaten.
- `one-to-one-graph-matching` erzeugt vorläufige Zuordnungen und Strukturprüfungen.
- `analytical-feedback` erstellt kompakte elementbezogene Hinweise.
- `feedback-generation` erzeugt die kompakte Feedbackprojektion.

Alle Workflow-Serviceversionen sind `1.0.0`, alle Artefaktverträge verwenden
`/v1` und alle Images den Tag `v1`. Die benötigten Modell- und Paarabläufe sind
intern in der einzigen Workflowdatei eingebettet.

Build und lokale Kubernetes-Bereitstellung sind in [dagu/README.md](../README.md)
beschrieben. Die übrigen Serviceordner enthalten frühere Vorlagen oder
Forschungsressourcen und werden vom Auswertungsworkflow nicht verwendet.
