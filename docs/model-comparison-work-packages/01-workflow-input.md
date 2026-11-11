# 01 – Vollständige Workflow-Eingabe vorbereiten

**Baustein:** API-Auswertungsstart und Container `workflow-data`, Schritt `prepare_input`.

**Abhängigkeiten:** Keine vorgelagerten Umsetzungspakete. Die [gemeinsamen Verträge](README.md) gehören zu diesem Auftrag.

**Stand:** Paket 01 ist umgesetzt und an den direkten Übergaben gezielt geprüft. `comparisonConfig` bleibt beim API-Start `{}`; zusätzliche Parameter und die Folgepakete sind weiterhin offen.

## Arbeitsziel

Ein Auswertungslauf erhält einen vollständigen, unveränderlichen Snapshot seiner Modelle und ein erweiterbares JSON-Objekt `comparisonConfig`. Dieses Paket legt die grundlegende Eingabehülle an. Welche konkreten Parameter die Vergleichsschritte benötigen, wird während ihrer Entwicklung festgelegt und hier anschließend nachgetragen.

Unterschiedliche Auswertungen können weiterhin unterschiedliche Workflows verwenden. `comparisonConfig` dient ergänzend der Parametrisierung des jeweils ausgewählten Workflows. Ein vollständiges Konfigurationsschema aller späteren Services ist kein Liefergegenstand dieses ersten Pakets.

## Ausgangslage und relevante Stellen

- [evaluations.py](../../api/src/modeling_api/services/evaluations.py): `start` und `_evaluation_input` sammeln bereits Modellversionen, Aufgabe, Musterlösungen und Sprachabhängigkeiten.
- [workflow-data/main.py](../../dagu/workflow-services/workflow-data/src/main.py): `prepare` validiert und veröffentlicht den Snapshot.
- [workflow_io.py](../../dagu/workflow-services/workflow_io.py): unveränderliche Artefakte und Prüfung der Eingabeschemaversion.

Der Snapshot enthält nun `comparisonConfig` und wird bei der Initialisierung um `inputHash` ergänzt. Die konkreten Vergleichsregeln und die Bedeutung mehrerer Referenzen werden in den jeweils zuständigen Folgepaketen bestimmt. Der Auswertungsdatensatz und die Startabsicht werden vor dem Dagu-Aufruf gespeichert; die Auswertungs-ID wird als vorab festgelegte Dagu-Laufkennung übergeben.

## Was kommt hinein?

| Eingabe | Inhalt |
|---|---|
| Abgabe | Gespeicherte Modellversion mit XML, `modelId`, `versionId`, `workspaceLanguages` |
| Aufgabe | Festgelegter Aufgabenrelease und dessen ausgewählter Auswertungsworkflow |
| Referenzen | Alle in diesem Release vorgesehenen vollständigen Musterlösungen mit Modellversionsbezug |
| Sprachen | Vollständige aufgelöste Sprachversionen einschließlich eingebundener Sprachen |
| Vergleichskonfiguration | JSON-Objekt `comparisonConfig`, zunächst auch `{}`; konkrete Parameter werden bei Bedarf ergänzt |

Der Browser übergibt weiterhin den Auswertungsauftrag für ein Modell. Er darf weder eine fremde Musterlösung auswählen noch die fachlichen Vergleichsregeln des Aufgabenrelease überschreiben. Der bestehende Checkpoint-Ablauf sorgt für einen gespeicherten Stand.

## Was kommt heraus?

`inputs/evaluation-input.json` enthält `evaluation-input/v1` mit:

| Feld | Garantie |
|---|---|
| `schema`, `schemaVersion` | `evaluation-input/v1`, `1` |
| `evaluationId` | Identität dieses Laufs |
| `task` | Aufgabenquelle und vollständiger Aufgabenstand |
| `models` | Genau eine Abgabe und mindestens eine Referenz; jeweils `source` und `snapshot` |
| `languages` | Aufgelöste, versionierte Definitionen |
| `comparisonConfig` | Für diesen Lauf übergebenes Konfigurationsobjekt; zunächst ohne vorgeschriebene Unterfelder |
| `inputHash` | Hash des gesamten fachlichen Eingabesnapshots nach den gemeinsamen Regeln |

Beispiel für die lauflokalen Quellen; XML und Definitionen sind hier ausgelassen:

```json
{
  "schema": "evaluation-input/v1",
  "schemaVersion": 1,
  "evaluationId": "evaluation-1",
  "models": [
    {
      "source": {
        "key": "submission",
        "role": "submission",
        "label": "Aktuelles Modell",
        "modelId": "model-s",
        "versionId": "version-s"
      }
    },
    {
      "source": {
        "key": "reference_1",
        "role": "reference",
        "label": "Musterlösung 1",
        "modelId": "model-r",
        "versionId": "version-r"
      }
    }
  ],
  "comparisonConfig": {}
}
```

Das erfolgreiche Initialisierungsergebnis benennt `evaluationId`, `inputHash`, `inputSnapshot`, `modelKeys` und `referenceKeys`. Es enthält keine Kopie sämtlicher Modellinhalte auf stdout.

`inputHash` ist SHA-256 über kanonisches UTF-8-JSON des gesamten Snapshots einschließlich `evaluationId` und `comparisonConfig`, ohne `inputHash`. Objektschlüssel und Identitätsmengen werden stabil sortiert; fachlich geordnete Listen bleiben erhalten. Technische Zeitstempel werden nicht aufgenommen. Details zur Kanonisierung stehen in der [Service-README](../../dagu/workflow-services/workflow-data/README.md). Workspace-Leser prüfen diesen Hash vor der Übergabe.

## Geplanter Arbeitsumfang

1. **Modelleingaben vollständig sammeln.** Abgabe, Aufgabe, Referenzversionen und ihre Sprachabhängigkeiten mit eindeutigen Quellen übernehmen. Die fachliche Interpretation dieser Inhalte bleibt Aufgabe der späteren Services.
2. **`comparisonConfig` anlegen und weitergeben.** Im Snapshot ein JSON-Objekt vorsehen. Wenn noch keine Konfiguration übergeben wird, `{}` verwenden. Vorhandene Einträge unverändert erhalten; keine vorläufigen Bereichsnamen oder Parameter als Pflichtfelder implementieren.
3. **Konfigurationsstand pro Lauf sichern.** Das tatsächlich übergebene Objekt zusammen mit den übrigen Eingaben unveränderlich speichern und in den Eingabehash einbeziehen. Die Unveränderlichkeit eines Laufs bedeutet nicht, dass das Konfigurationsschema für die weitere Entwicklung bereits abgeschlossen ist.
4. **Grundlegende Validierung und bestehende Grenzen erhalten.** Modellquellen, Rollen, Versionen, Sprachabhängigkeiten und den Objekttyp von `comparisonConfig` prüfen. Das bestehende Startnutzlastlimit berücksichtigen. Fachliche Parameterprüfung, neue Element-/Paargrenzen und Verarbeitungsvorgaben werden erst mit dem jeweiligen Verbraucher eingeführt.
5. **Snapshot veröffentlichen.** Die nachgelagerten Workspace-Leser auf die vorgesehene V1-Eingabehülle abstimmen. Bestehende Definitionen direkt anpassen; für den ersten Release sind weder eine V2 noch eine Altformat-Konvertierung erforderlich. Weder ein leeres Objekt noch noch unbekannte Konfigurationseinträge sind allein ein Initialisierungsfehler.
6. **Start eindeutig zuordnen.** Auswertungsidentität und Startabsicht vor dem Dagu-Aufruf festhalten, anschließend die Laufkennung zuordnen. Ein fehlgeschlagener oder unklarer Start bleibt als solcher sichtbar. Bei unbekanntem Ausgang des Startaufrufs nicht blind einen zweiten Lauf auslösen; zunächst anhand der übergebenen Auswertungsidentität zuordnen beziehungsweise einen technischen Klärungsstatus ausgeben.
7. **Bei tatsächlichem Bedarf nachtragen.** Benötigt ein Folgepaket einen Parameter, wird dort dessen fachlicher Vertrag festgelegt. Im selben Zuge werden dieses Eingabedokument, die README und die betroffenen Übergaben ergänzt. Erst dann werden gegebenenfalls nötige Auflösung und Validierung an der Eingabegrenze erweitert.

Die konkrete Persistenz- und Aufrufimplementierung bleibt der Umsetzung überlassen. Eine neue Workflowplattform oder allgemeine Konfigurationsverwaltung ist nicht Teil des Pakets.

## Nachgelagerte Konkretisierung der Konfiguration

Die [Konfigurationsreferenz in der README](README.md#workflow-auswahl-und-vorläufige-konfigurationsreferenz) dient der Orientierung. Ihre Bereichsnamen und Inhalte sind kein finales Schema. Für Paket 01 genügt `comparisonConfig: {}`.

| Thema | Konkretisierung bei tatsächlichem Bedarf |
|---|---|
| Allgemeine Definitionsauflösung, Container und vorhandene Kindbestandteile | Paket 02 – Graph-Parser; keine Beschränkung auf eine Sprache, kein Pflichtprofil und keine sprachspezifische Textgrammatik |
| Semantische Verfahren und Aliaswissen | Paket 04 – Synonym-Matching |
| Kriterien, Gewichte, Schwellen und plausible Kandidaten | Paket 05 – One-to-One-Graph-Matching |
| Bedeutung mehrerer Referenzen und Auswahlregeln | Paket 06 – Gesamtergebnis |
| Verarbeitungslimits | Im betroffenen Verarbeitungsschritt; Laufzeitintegration in Paket 07 |
| Offenlegung von Ergebnissen | Paket 08 – Ergebnisintegration |

Diese Themen müssen nicht vor Abschluss von Paket 01 vollständig parametrisiert sein. Sobald eine konkrete Einstellung benötigt wird, werden Name, Datentyp, Bedeutung, Standardverhalten und Validierungszuständigkeit festgelegt und die Eingabedokumentation aktualisiert. Das Objekt wird dadurch schrittweise erweitert, ohne vergangene Auswertungssnapshots nachträglich zu ändern.

### Allgemeine Übergabe an Paket 02

Die zuvor eingeführten sprachspezifischen Profil-, Typ-Mapping- und Attributgrammatikparameter sind keine gültige Voraussetzung mehr. Paket 02 verarbeitet die vorhandene Modellstruktur und die mitgelieferten Sprachdefinitionen allgemein. Die Initialisierung übergibt weiterhin das erweiterbare Konfigurationsobjekt; bei leerem Objekt wird kein besonderes Sprachprofil vorausgesetzt. Nur tatsächlich benötigte allgemeine Optionen dürfen später ergänzt werden.

Die Umsetzung führt keine zusätzlichen Parameter ein. Der [V1-Servicevertrag](../../dagu/workflow-services/graph-parser/README.md) dokumentiert die direkte Übergabe des vollständigen Snapshots, die Modellwahl und die Herkunftsfelder `languageResources`, `producer` und `graphHash`. Die Initialisierung aus Paket 01 bleibt unverändert.

### Übergabe an Paket 04 ohne neue Parameter

Paket 04 verarbeitet im eigenen Service `synonym-matching` genau zwei Inventare
mit dem übernommenen semantischen Standard. `comparisonConfig: {}` bleibt
ausreichend; `comparisonConfig.semantics` darf fehlen oder leer sein. Nicht
unterstützte Einträge oder andere Datentypen in diesem Bereich werden vom
Semantikschritt abgewiesen. Andere Bereiche prüft weiterhin erst ihr zuständiger
Verbraucher. Es gibt keine neuen Methoden-, Alias-, Gewichts- oder Filterparameter.
Der [Servicevertrag](../../dagu/workflow-services/synonym-matching/README.md)
beschreibt die tatsächliche V1-Übergabe und die im Ergebnis dokumentierte
aufgelöste Konfiguration. Die Initialisierung bleibt unverändert.

## Fehlerverhalten

Fehlende Modellversionen, fehlende Sprachdefinitionen, keine Referenz, widersprüchliche Quellen oder ein anderer Datentyp als ein JSON-Objekt für `comparisonConfig` verhindern den Start der fachlichen Pipeline. Ein leeres Konfigurationsobjekt und noch nicht von der Initialisierung verstandene Einträge sind zulässig. Fachlich ungültige konkrete Parameter prüft der dafür zuständige Verbraucher nach seinem dann definierten Vertrag. Ein gültiges, inhaltlich leeres Modell ist zulässig. Nach dem Start wird keine neuere Modell- oder Sprachversion nachgeladen.

Die Startabsicht wird intern als `startStatus: starting` gespeichert, ein bestätigter Start als `started`. Eine ausdrückliche Ablehnung bleibt mit `failed`, ein unklarer Ausgang mit `unknown` und technischer Fehlerangabe erhalten. Die API liefert jeweils die angelegte Auswertung mit ihrer Identität zurück. Erneute Startaufrufe für dieselbe Modellversion und denselben Workflow liefern bei `starting` oder `unknown` die vorhandene Auswertung. Der Detailabruf sucht den Dagu-Lauf anhand der festgelegten Kennung und übernimmt ihn, sobald er gefunden wird; andernfalls liefert er einen verständlichen Klärungsstatus im bestehenden Schrittformat. Er startet keinen Ersatzlauf. Die öffentliche API-Hülle benötigt dafür keine neue Zustandsmenge und keine optionale Laufkennung.

## Erfüllungskriterien

- [x] Alle Modelle und der für diesen Lauf übergebene Konfigurationsstand sind im veröffentlichten Snapshot erhalten.
- [x] Genau eine Abgabe und die vollständige Referenzliste sind mit unveränderlichen Modellversionen verbunden.
- [x] `comparisonConfig` ist als JSON-Objekt vorhanden und darf ohne konkrete Unterfelder leer sein.
- [x] Die Initialisierung verlangt keine erst für Folgepakete vorgeschlagenen Parameter und erhält vorhandene Einträge verlustfrei.
- [x] README und Eingabedokument benennen die Konfigurationsbereiche als vorläufige Referenz und den Ablauf für spätere Ergänzungen.
- [x] Die Initialisierung kann identisch wiederholt werden; ein anderer Inhalt überschreibt den vorhandenen Snapshot nicht.
- [x] Ungültige Eingaben werden vor fachlicher Verarbeitung als technische beziehungsweise Konfigurationsfehler gemeldet.
- [x] Ein Startfehler verliert die Auswertungsidentität nicht und verursacht keinen unkontrollierten Doppelstart.

**Aktuelle Verifikation:** Ausschließlich statische Durchsicht der Änderungen und Schnittstellen. Keine Tests erstellen, erweitern oder ausführen; keine manuellen Modell-/Containerläufe, Builds, Benchmarks, Lint- oder Syntaxprüfungen. Die Kriterien beschreiben Sollverhalten und sind derzeit kein Auftrag zur Ausführung.

**Durchgeführte Verifikation:** API-Sammlung mit aufgelösten Sprachabhängigkeiten → gzip/Base64 → Initialisierung → Workspace → bestehender Parser für ein gültiges leeres Modell; zusätzlich unbekannte Konfigurationseinträge, hashrelevante Konfigurationsänderung, identische Wiederholung, Schreibkonflikt und manipulierten Hash geprüft. Fehlende Referenzen oder Sprachen, unvollständige Referenzlisten, widersprüchliche Quellen/Rollen/Aufgabenbezüge und falsche Konfigurationstypen wurden vor Veröffentlichung abgewiesen. Mit simuliertem HTTP-Transport und Datenbankspeicher wurden bestätigter und abgelehnter Start, Zeitüberschreitung, ungültige Antworten, Serverfehler, Konflikt, Abbruch nach Speicherung der Startabsicht sowie spätere Laufzuordnung ohne erneuten Start nachvollzogen. Das vorhandene Startnutzlastlimit und das Verbot einer Browser-Konfigurationsüberschreibung wurden geprüft. Keine neuen Testdateien oder vollständigen Testsuiten; kein Live-Nachweis gegen MongoDB, Dagu oder Kubernetes.

Zusätzlich wurde der tatsächliche `workflow-data`-CLI-Aufruf für Erfolg und ungültige Konfiguration ausgeführt: kompakte V1-Ausgabe auf stdout, Fehler auf stderr und kein Erfolgsartefakt im Fehlerfall. Der bestehende Browser-Starthandler wurde mit simulierten Antworten für bestätigten, unklaren und abgelehnten Start sowie Anfragefehler ausgeführt; Checkpoint und Auswahl der Auswertung bleiben erhalten. Gezieltes ESLint der betroffenen Vue-Datei und die Python-Syntaxprüfung waren erfolgreich. Ein Browserdurchlauf der gesamten Anwendung war nicht Teil dieses Nachweises.

**Übergabe:** [02 – Graph-Parser](02-graph-parser.md) erhält den Snapshot und das zunächst einfache Konfigurationsobjekt. Wenn der Parser konkrete Einstellungen benötigt, werden sie in Paket 02 definiert und hier entsprechend nachgetragen.
