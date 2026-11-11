# workflow-data

Prüft und speichert den Auswertungs-Snapshot unveränderlich unter
`inputs/evaluation-input.json` im Laufordner.

- Eingabe: `evaluation-input/v1` als UTF-8-JSON, gzip-komprimiert und Base64-kodiert
  über `EVALUATION_INPUT_GZIP_BASE64`.
- `WORKFLOW_EVALUATION_ID` muss mit `evaluationId` übereinstimmen.
- Der Snapshot enthält `task`, `models` mit `source` und `snapshot` sowie sämtliche
  referenzierten Sprachversionen unter `languages` einschließlich Abhängigkeiten.
  Genau eine Abgabe und alle Referenzen des Aufgabenrelease sind erforderlich;
  Quellen und Snapshot-Versionen müssen übereinstimmen.
- `comparisonConfig` ist ein erweiterbares JSON-Objekt, standardmäßig `{}`.
  Unbekannte Einträge werden unverändert gesichert; es gibt noch keine fachlichen
  Parameter oder vorgeschriebenen Unterbereiche. Andere Datentypen werden abgelehnt.
- Die Initialisierung ergänzt `inputHash` als SHA-256 des vollständigen Snapshots
  einschließlich Konfiguration und Auswertungs-ID, ohne das Hashfeld selbst.
  Das kanonische UTF-8-JSON verwendet sortierte Objektschlüssel, keine zusätzlichen
  Leerzeichen und keine ASCII-Escapes. Modelle, Sprachversionen, Sprachreferenzen
  und die Musterlösungsreferenzen der Aufgabe werden für den Hash nach Identität
  sortiert; fachlich geordnete Listen behalten ihre Reihenfolge. Laufzeitangaben
  werden nicht in den Snapshot aufgenommen.
- Ausgabe: `workflow-result/v1` mit `evaluationId`, `inputHash`, `inputSnapshot`,
  `modelKeys`, `referenceKeys` und `modelCount` unter `result`, ohne Modellinhalte.
- Identische Wiederholungen sind zulässig. Abweichender Inhalt am selben Pfad
  ist ein Konflikt; ungültige Eingaben veröffentlichen kein erfolgreiches Artefakt.

Vertrag und Eingangsprüfungen: `EvaluationInput` und `prepare()` in `src/main.py`.
Nachfolgende Dienste lesen den Snapshot über `workspace().snapshot()`.
Dieser Zugriff prüft V1, Auswertungs-ID, Konfigurationsobjekt und Eingabehash.
