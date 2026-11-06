# template-service

Ein gewöhnliches Python-Skript: JSON-Objekt hinein, JSON-Objekt auf stdout,
Fehler auf stderr, Exit-Code `0` bei Erfolg. Keine Registrierung, keine
Handler-Basisklasse und kein geladenes Schema erforderlich.

## Vollständiges Ein-/Ausgabebeispiel

Eingabe über `TEMPLATE_INPUT` oder stdin:

```json
{"message": "hello"}
```

Ausgabe ohne Laufkontext:

```json
{
  "status": "ok",
  "capability": "template-service",
  "summary": "Template erfolgreich ausgeführt",
  "result": {"echo": {"message": "hello"}}
}
```

`status`, `summary` und `result` machen die Ausgabe für die bestehende UI lesbar.
Dies ist eine dokumentierte Konvention; Dagu prüft dieses JSON nicht gegen ein
Dienstschema. Fachlogik und deren notwendige Prüfungen bleiben im Dienst.

Mit `WORKFLOW_EVALUATION_ID` kann der Dienst `workspace().snapshot()` lesen.
`WORKFLOW_INPUT_PATH` liest eine konkrete JSON-Datei aus diesem Laufordner;
`WORKFLOW_OUTPUT_PATH` speichert die Ausgabe an einem ausdrücklich gewählten
relativen Pfad. Der Aufrufer wählt die Pfade und damit die Datenabhängigkeiten.

Build aus `dagu/workflow-services/`:

```bash
docker build -f template-service/Dockerfile -t template-service:0.2.0 .
docker run --rm -e TEMPLATE_INPUT='{"message":"hello"}' template-service:0.2.0
```

Speicher und Ablauf: [Datenfluss einer Auswertung](../../README.md#datenfluss-einer-auswertung).
