# 06 – Referenzvergleiche zu einem Gesamtergebnis zusammenführen

**Baustein:** Neuer kleiner Workflow-Container `comparison-result`, Abschlussschritt `collect_comparison`.

**Abhängigkeit:** [05 – One-to-One-Graph-Matching](05-one-to-one-graph-matching.md). Es gelten die [gemeinsamen Verträge](README.md).

**Stand:** Geplant, nicht implementiert. Der aktuelle Hauptworkflow endet nach Phase 4 mit einem Vorschau-Manifest; der hier beschriebene fachliche Gesamtabschluss gehört zum späteren Umfang.

## Arbeitsziel

Alle erwarteten Referenzvergleiche werden in genau einem fachlichen Gesamtergebnis erfasst. Eine maßgebliche Referenz wird nur mit nachvollziehbarer Grundlage ausgewählt. Fehlende Ergebnisse und konkurrierende Alternativen bleiben sichtbar.

## Ausgangslage und Abgrenzung

Der Hauptworkflow veröffentlicht bisher nur Pfade und Zähler. Der Container [feedback-generation](../../dagu/workflow-services/feedback-generation/src/main.py) ist ein Demo-Aggregator ohne fachliche Bewertung. Dieser Auftrag schafft einen ausdrücklich benannten Vergleichsabschluss. Er erzeugt weder Noten noch didaktische Hinweise und benötigt keinen dauerhaft laufenden Dienst.

## Was kommt hinein?

| Eingang | Inhalt |
|---|---|
| `WORKFLOW_EVALUATION_ID` | Laufbezug |
| Eingabesnapshot | Erwartete Referenzen, Originalmodellquellen, `referencePolicy` und Auswahlprofil |
| Einzelvergleiche | Vorhandene Dateien `comparisons/<referenceKey>.json` |
| `WORKFLOW_OUTPUT_PATH` | `results/comparison.json` |

Der Schritt läuft erst, wenn alle vorgesehenen Referenzzweige beendet oder endgültig nicht ausführbar sind. Diese Voraussetzung garantiert Paket 07. Er fragt weder die Datenbank noch Dagu selbst ab.

Die Referenzliste stammt aus dem Snapshot. Ein Verzeichnisscan allein darf keine vollständige Liste erfolgreicher und ausgefallener Referenzen vortäuschen.

## Was kommt heraus?

Eine `workflow-result/v1`-Hülle mit `capability: comparison-result` und:

| Feld in `result` | Inhalt |
|---|---|
| `schema` | `comparison-result/v1` |
| `evaluationId`, `inputHash`, `submission`, `producer` | Lauf und unveränderliche Grundlagen |
| `referencePolicy` | Initial `complete_alternatives` |
| `disclosure` | Unveränderte Offenlegungsregeln aus dem Eingabesnapshot für die spätere API-Projektion |
| `referenceResults` | Genau ein Eintrag je erwarteter Referenz: Quelle, Verfügbarkeit, eigene Verfügbarkeitsdiagnose und bei gültigem Ergebnis `comparisonPath` sowie dessen Eingabe-/Verarbeitungsbezüge |
| `selectedReferenceKey` | Begründet ausgewählte Referenz oder `null` |
| `selection` | Regel, berechnete Abweichungsbereiche, Begründung und gegebenenfalls konkurrierende Referenzen |
| `resultStatus` | `complete`, `partial` oder `unavailable` |
| `completeness` | Technische Abdeckung, Interpretation und Zuordnung getrennt |
| `assessmentAvailable` | Initial `false` |
| `warnings`, `errors` | Eigene Abschluss-/Auswahlprobleme und Referenzen auf vorgelagerte Ursachen, keine kopierten Diagnoselisten |

`referenceResults` referenziert die separat gespeicherten Einzelvergleiche. Zuordnungen, offene Gruppen, Befunde und Vergleichseinheiten werden für die Aggregation gelesen, aber nicht vollständig in das Gesamtartefakt kopiert. Eigene Ergebnisse dieses Schritts sind Verfügbarkeit, Abweichungsbereiche, Gesamtabdeckung und Referenzauswahl. Eine studentische Projektion entsteht erst in Paket 08.

## Geplanter Arbeitsumfang

### 1. Erwartete und vorhandene Ergebnisse abgleichen

Für jede erwartete Referenz wird die entsprechende Datei gelesen und gegen Quelle, Paar, Eingabehashes und Vergleichsprofil geprüft. Es gelten drei unterschiedliche Situationen:

- **Verfügbar:** Der Einzelvergleich erfüllt seinen Vertrag. Er kann fachlich trotzdem eingeschränkt sein.
- **Nicht verfügbar:** Es gibt nach Ende des Zweigs kein Ergebnis, etwa wegen eines Parser- oder Matchingfehlers.
- **Ungültig:** Eine Datei existiert, gehört aber zum falschen Lauf/Paar oder verletzt den Vertrag.

Nicht verfügbare und ungültige Ergebnisse bleiben als eigene Einträge erhalten. Andere gültige Vergleiche dürfen weiterhin veröffentlicht werden. Fehlende Dateien werden hier als fehlendes Verarbeitungsergebnis bezeichnet; genaue Prozessursachen ergänzt Paket 08 aus Dagu.

### 2. Normalisierte strukturelle Abweichung bestimmen

Die in Paket 05 gelieferten `comparisonUnits` werden einmalig gezählt. Pro Einheit ist `w = referenceWeight + studentWeight`. Die Grenzen der Gesamtabweichung sind:

```text
lower = sum(w * deviation.lower) / sum(w)
upper = sum(w * deviation.upper) / sum(w)
```

Das Auswahlprofil bestimmt die fachlichen Gewichte und die Abweichung zugeordneter Einheiten. Technische Kanten zählen nicht mit. Eine eindeutig fehlende oder zusätzliche Einheit trägt Abweichung 1; eine passende Einheit 0. Offene Bereiche bleiben Bereiche.

Der Aggregator prüft gegen `coverage`, dass die Vergleichseinheiten und Gewichte pro Seite die im Einzelvergleich inventarisierten fachlichen Instanzen genau einmal abdecken. Er erzeugt keine neuen Elementzuordnungen und korrigiert keine widersprüchlichen Befunde nach eigenem Ermessen.

Sind beide fachlichen Mengen leer, ist der Nenner null. Dieser Fall wird ausdrücklich behandelt: rechnerisch gibt es keine Abweichung, aber eine leere Referenz ist standardmäßig keine zulässige Musterlösung. Nur eine im Aufgabenprofil ausdrücklich erlaubte leere Referenz darf als reguläre Alternative teilnehmen. Eine leere Abgabe gegen eine nichtleere Referenz ist dagegen regulär vergleichbar.

Die Werte liegen zwischen 0 und 1, sind strukturelle Abweichungen und keine Noten. Unterschiedliche Modellgrößen werden normalisiert; fachlich unterschiedliche Granularität kann trotzdem nur über das vereinbarte Profil beziehungsweise zugelassene Referenzalternativen beurteilt werden.

### 3. Referenz konservativ auswählen

- Bei genau einer erwarteten, gültigen und vollständig interpretierten Referenz ist diese der Vergleichsbezug. Offene Zuordnungen innerhalb dieses Vergleichs bleiben offen.
- Bei mehreren Referenzen müssen alle erwarteten Alternativen verfügbar und für die Auswahl ausreichend interpretiert sein.
- Eine Referenz wird maßgeblich, wenn ihre obere Abweichungsgrenze kleiner als die untere Grenze jeder anderen Referenz ist. Eine gegebenenfalls konfigurierte Auswahlmarge wird zusätzlich berücksichtigt; ohne fachlich festgelegte Marge gilt 0.
- Überlappende Bereiche oder Gleichstände ergeben `selectedReferenceKey: null` und eine begründete Liste verbleibender Alternativen.
- Bei einem ausgefallenen Referenzzweig bleibt die Auswahl ebenfalls offen. Die vorhandenen Vergleiche werden trotzdem ausgegeben.

Beispiel mit rein illustrativen Werten: `[0.10, 0.15]` gegen `[0.30, 0.40]` erlaubt die erste Referenz als maßgeblich. `[0.10, 0.35]` gegen `[0.20, 0.30]` erlaubt keine eindeutige Auswahl.

### 4. Gesamtstatus bestimmen

| Situation | `resultStatus` |
|---|---|
| Alle Vergleiche verfügbar und interpretiert; Zuordnungen und gegebenenfalls Referenzauswahl entschieden | `complete` |
| Mindestens ein nutzbarer Vergleich, aber technischer Teilfehler, Interpretationslücke, offene Zuordnung oder offene Referenzauswahl | `partial` |
| Kein nutzbarer Vergleich oder grundlegender Konfigurationsfehler | `unavailable` |

Auch ein vollständiges Ergebnis kann viele fachliche Fehler enthalten. `complete` bedeutet vollständige Auswertbarkeit, nicht eine korrekte Abgabe.

### 5. Herkunft und Integrität erhalten

Ergebnisse verschiedener Referenzen werden nicht zu einer künstlichen Musterlösung zusammengesetzt. Das Gesamtergebnis ist ein Verzeichnis vollständiger Alternativvergleiche mit begründeter Auswahl, keine neue Matchingentscheidung über ihre Teilbefunde.

Fehlplatzierung und abhängige Befunde behalten ihre `groupId`- und `blockedBy`-Bezüge. Die spätere Bewertung kann dadurch Teilpunkte vergeben, ohne technische Kanten oder Folgefehler mehrfach zu bestrafen.

## Beispiel für einen Teilabschluss

Gekürzter geplanter Ergebnisinhalt; der verfügbare Einzelvergleich bleibt separat gespeichert und wird über `comparisonPath` referenziert:

```json
{
  "schema": "comparison-result/v1",
  "evaluationId": "evaluation-1",
  "referencePolicy": "complete_alternatives",
  "referenceResults": [
    {
      "referenceKey": "reference_1",
      "availability": "available",
      "comparisonPath": "comparisons/reference_1.json"
    },
    {
      "referenceKey": "reference_2",
      "availability": "unavailable",
      "reasonCode": "REFERENCE_RESULT_UNAVAILABLE"
    }
  ],
  "selectedReferenceKey": null,
  "selection": { "reasonCode": "REFERENCE_SET_INCOMPLETE" },
  "resultStatus": "partial",
  "completeness": {
    "technical": "partial",
    "interpretation": "complete",
    "mapping": "partial"
  },
  "assessmentAvailable": false
}
```

`interpretation` und `mapping` beschreiben die verfügbaren Vergleiche; die technische Dimension und `referenceResults` machen fehlende Zweige ausdrücklich sichtbar. Im Beispiel besitzt der verfügbare Vergleich zusätzlich eine offene Zuordnung. Ohne nutzbaren Einzelvergleich lauten alle drei Vollständigkeitsdimensionen `unavailable`.

## Fehlerverhalten

Ein fehlendes oder ungültiges einzelnes Paarergebnis wird zum Teilabschluss. Ein nicht lesbarer Eingabesnapshot verhindert dagegen einen vertrauenswürdigen Abschluss. Kann `results/comparison.json` nicht veröffentlicht werden, ist dies ein technischer Abschlussfehler; die API darf dann kein vorheriges Teilartefakt zum Gesamtergebnis erklären.

Ein erfolgreich erzeugtes `unavailable`-Ergebnis bedeutet, dass die Zusammenführung funktioniert hat, aber kein fachlicher Vergleich vorliegt. Diese Aussage bleibt vom Dagu-Prozessstatus unterscheidbar.

## Erfüllungskriterien

- [ ] Jede erwartete Referenz erscheint genau einmal, auch ohne Ergebnisdatei.
- [ ] Modellquellen und Paarergebnisse bleiben getrennt und vollständig zuordenbar.
- [ ] Die strukturelle Auswahlmetrik zählt fachliche Einheiten einmalig und behandelt den leeren Nenner ausdrücklich.
- [ ] Eine Referenz wird nur gemäß der dokumentierten Auswahlregel maßgeblich.
- [ ] Fehlende Referenzen und Gleichstände erzeugen keine behauptete eindeutige Auswahl.
- [ ] Das Gesamtergebnis erhält Unsicherheit, Befundabhängigkeiten und Originalreferenzen und enthält keine Note.

**Aktuelle Verifikation:** Ausschließlich statische Durchsicht der Änderungen und Schnittstellen. Keine Tests erstellen, erweitern oder ausführen; keine manuellen Modell-/Containerläufe, Builds, Benchmarks, Lint- oder Syntaxprüfungen. Die Kriterien beschreiben Sollverhalten und sind derzeit kein Auftrag zur Ausführung.

**Übergabe:** [07 – Dagu-Workflow](07-dagu-workflow.md) veröffentlicht den festen Ergebnispfad; [08 – Ergebnisintegration](08-result-integration.md) stellt den Inhalt kontrolliert bereit.
