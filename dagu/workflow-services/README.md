# Workflow-Services für die Modellauswertung

`model-evaluation-graph-matching` verwendet sieben eigenständige Service-Images:

- `workflow-data` validiert und speichert den eingefrorenen Eingabesnapshot.
- `graph-parser` normalisiert die Modellgraphen.
- `model-label-extraction` extrahiert die Elementinventare.
- `synonym-matching` berechnet semantische Kandidaten.
- `one-to-one-graph-matching` erzeugt vorläufige Zuordnungen und Strukturprüfungen.
- `analytical-feedback` erstellt kompakte elementbezogene Hinweise.
- `feedback-generation` erzeugt die kompakte Feedbackprojektion.

Graph Matching verwendet Serviceversion `2.2.0` und Image `v6`, Analytical
Feedback `2.2.1` und Image `v10`, Synonym Matching `1.1.0` und Image `v2`.
Feedback Generation verwendet `2.2.0`/`v9`, Workflow-Data Image `v2`, die übrigen Dienste `1.0.0`/`v1`.
Der Hauptworkflow ist `v12`. Graphvergleich verwendet `reference-comparison/v2`,
Analyse und Feedback `/v3`; übrige Artefakte und stdout-Envelopes bleiben `/v1`.
Matcher-Fakten tragen Version `1.1`, Identitätsevidenzen `1.1`.
Analytical Feedback und Feedback Generation kopieren beim Build Dateien anderer
Dienste (`artifacts.py`, `graph_index.py` bzw. `analysis_contract.py`); Änderungen
daran erfordern auch dort neue Image-Tags.
Historische Analyserevisionen bleiben lesbar.
Die benötigten Modell- und Paarabläufe sind
intern in der einzigen Workflowdatei eingebettet.

Build und lokale Kubernetes-Bereitstellung sind in [dagu/README.md](../README.md)
beschrieben. Die übrigen Serviceordner enthalten frühere Vorlagen oder
Forschungsressourcen und werden vom Auswertungsworkflow nicht verwendet.
