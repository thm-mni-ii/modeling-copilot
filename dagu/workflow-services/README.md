# Durchspielbare Workflow-Services

Die fünf Capability-Images sind eigenständige Services: jedes Verzeichnis
enthält Dockerfile, Source, Eingabe-/Ausgabe-Schema, Capability-Metadaten,
README und Test. Sie führen keine Fachlogik aus, geben jedoch strukturierte,
deterministische Dummy-Ergebnisse auf stdout aus. Die Workflow-Schritte nutzen
eine viersekündige Verzögerung, damit parallele und abhängige Status im
Frontend sichtbar werden.

## Lokal bauen und prüfen

```bash
docker compose --profile workflow-services build
docker run --rm -e TEMPLATE_INPUT='{"step":"graph_parser"}' modeling-copilot/graph-parser:0.1.1
```

Docker-Desktop-Kubernetes kann lokal gebaute Images mit
`image_pull_policy: IfNotPresent` verwenden. Für K3s müssen die Images vor dem
Start in eine für den Cluster erreichbare Registry gepusht und die Image-Namen
im Workflow auf diese versionierten Registry-Tags geändert werden.
