# 08 – Vergleichsergebnis in API und vorhandener Sidebar bereitstellen

**Baustein:** Bestehende Auswertungs-API, Ergebnisservice und `EvaluationSidebar`.

**Abhängigkeiten:** [06 – Gesamtvertrag](06-comparison-result.md) und [07 – Workflow-Ausführung](07-dagu-workflow.md). Es gelten die [gemeinsamen Verträge](README.md).

**Stand:** Status, getrennte JSON-Zwischenergebnisse und Vorschau-Manifest bis Phase 4 sind an die vorhandene API und Sidebar angebunden. Die hier beschriebene fachliche Projektion, Offenlegung und historische Persistierung des Gesamtergebnisses bleiben geplant. Die zuletzt geänderten Artefaktverträge sind nur statisch durchgesehen; keine neue Laufzeitprüfung.

## Arbeitsziel

Nutzer sehen zur ausgewerteten Modellversion ein verständliches Vergleichsergebnis mit klar getrennten fachlichen Befunden, offenen Zuordnungen und technischen Problemen. Die Anzeige funktioniert auch bei Teilfehlern und gibt keine vollständigen Musterlösungen über generische JSON-Ergebnisse preis.

Dieses Paket ist der einzige eigenständige Anwendungsschritt außerhalb der Workflow-Container. Es schließt die Datenpipeline an den vorhandenen Nutzungsvorgang an.

## Ausgangslage und relevante Stellen

- [evaluations.py – Service](../../api/src/modeling_api/services/evaluations.py): Status, Unterläufe und bisherige Ableitung von `finalResult`.
- [evaluations.py – Schema](../../api/src/modeling_api/schemas/evaluations.py): bestehender API-Ergebnisvertrag.
- [evaluation.service.ts](../../web/src/services/evaluation/evaluation.service.ts): API-Grenze im Frontend.
- [EvaluationSidebar.vue](../../web/src/components/modeling/sidebars/EvaluationSidebar.vue): Verlauf, Polling und JSON-Darstellung.
- [ViewModeling.vue](../../web/src/views/ViewModeling.vue): Auslösen der Auswertung nach einem Checkpoint.

Die bestehende Nutzung und die Sidebar werden ergänzt. Ein neuer Ergebnisbereich, eine neue Rollenplattform oder die vollständige didaktische Feedbackfunktion sind nicht erforderlich.

## Was kommt hinein?

| Eingang | Inhalt |
|---|---|
| Auswertungsdatensatz | Besitzer, Abgabeversion, Aufgabenrelease, `evaluationId`, `dagRunId` |
| Dagu-Status | Technischer Zustand und Modell-/Paarunterläufe |
| Benanntes Gesamtartefakt | `results/comparison.json` aus dem Abschluss |
| Offenlegungsregeln | Als `disclosure` im Gesamtergebnis erhaltenes `comparisonConfig.disclosure` und bestehende Zugriffsrechte |
| Aktueller Modellkontext | Im Frontend geöffnete Modellversion beziehungsweise inzwischen bearbeiteter Stand |

## Was kommt heraus?

Eine kontrollierte Auswertungsantwort innerhalb der bestehenden API. Sie enthält:

- technischen Laufstatus und lesbare Schrittstatus;
- die analysierte Modellversion;
- fachlichen `resultStatus` und Vollständigkeitsangaben;
- studentisch sichtbare Befunde mit Originalzellbezügen der Abgabe;
- offene Zuordnungen in verständlicher Form;
- Angaben dazu, ob eine Referenz eindeutig maßgeblich ist;
- technische Einschränkungen ohne Umdeutung zu Modellfehlern;
- `assessmentAvailable: false` und keinen erfundenen Punktestand.

Das interne Gesamtergebnis und die studentische Ausgabe sind nicht identisch. Die Projektion wird serverseitig vorgenommen.

## Geplanter Arbeitsumfang

### 1. Ergebnis ausdrücklich laden und prüfen

Die API lädt ausschließlich das durch den Workflow benannte Gesamtartefakt. Vor der Verwendung prüft sie Schema, `evaluationId`, Abgabeversion und erwartete Referenzbezüge. Der Fallback auf das letzte beliebige strukturierte Schrittergebnis entfällt für diese Pipeline.

Im geplanten Gesamtartefakt referenziert `referenceResults` die Einzelvergleiche per `comparisonPath`. Die API löst die für die Anzeige notwendigen Referenzen innerhalb desselben Auswertungsbereichs auf und prüft deren Lauf-/Modellbezüge. Diese Anzeigeprojektion ist kein erneutes Einbetten vollständiger Vorgängerartefakte in die Workflow-Ergebnisse.

Ein gültiges Teilergebnis wird auch dann angezeigt, wenn der Dagu-Lauf wegen eines fehlgeschlagenen Zweigs insgesamt einen Fehlerstatus trägt. Umgekehrt wird ein technisch erfolgreicher Lauf ohne gültiges Gesamtartefakt als fehlendes Ergebnis erklärt.

### 2. Abgeschlossenes Ergebnis erhalten

Das validierte Gesamtartefakt und die für die historische fachliche Anzeige daraus aufgelösten Daten werden idempotent beim bestehenden Auswertungsdatensatz gespeichert. Das Lesen einer bereits gespeicherten abgeschlossenen Anzeige benötigt keine erneute Rekonstruktion aus Logs oder inzwischen entfernten Artefakten. Ein abweichendes Endergebnis unter derselben Auswertungsidentität ist ein Konflikt.

Dafür ist keine neue Datenbank oder allgemeine Artefaktplattform vorgesehen. Große Kandidatenmatrizen und Rohgraphen bleiben Workflow-Artefakte. Die gespeicherten fachlichen Präsentationsdaten enthalten genug Befunde, Quellen, Kriterien und Einschränkungen für die historische Ergebnisanzeige; vollständige Zwischenartefakte werden dafür nicht kopiert. Eine dauerhafte Aufbewahrung aller Rohartefakte wird damit nicht automatisch eingeführt. Diese Persistierung und Projektion ist noch nicht implementiert.

### 3. Unterläufe und technische Ursachen verbinden

Parser-/Inventarschritte werden nach Modellquelle, Semantik-/Matching-Schritte nach Referenzpaar zugeordnet. Fehlende Ergebnisse aus Paket 06 können so um die tatsächliche technische Ursache ergänzt werden. Eine allgemeine Verfügbarkeitsdiagnose wird nicht nachträglich als studentischer Modellfehler ersetzt.

Für einen abgebrochenen oder technisch unvollständigen Lauf bleiben die vorhandenen Schritte sichtbar. Ohne gültiges Gesamtartefakt bleibt `finalResult` leer; die Anzeige behauptet dann keinen fachlichen Abschluss.

### 4. Studentische Projektion festlegen

Die Projektion verwendet eine ausdrückliche Liste erlaubter Felder. Sie wird sowohl auf das Gesamtergebnis als auch auf Schrittresultate, Zusammenfassungen und Fehlermeldungen angewendet. Eine ausgeblendete Referenz im Hauptbereich reicht nicht, wenn derselbe Inhalt noch im JSON eines Parserunterlaufs steht.

| Interner Inhalt | Studentische Ausgabe im initialen Umfang |
|---|---|
| Originalelement der Abgabe | Zell-ID, eigener Labeltext und Befund dürfen sichtbar sein |
| Falscher Besitzer | Hinweis auf die betroffene Abgabeinstanz und die abweichende Zugehörigkeit |
| Erwarteter Besitzer aus der Referenz | Nur bei ausdrücklicher Freigabe; sonst keine Referenznamen |
| Offene Kandidaten mit Referenzlabels | Verständlicher Mehrdeutigkeitsstatus; keine automatische Offenlegung aller erwarteten Begriffe |
| Fehlendes Referenzelement | Abstrakter Befund beziehungsweise freigegebene Information; kein erfundenes Abgabeelement |
| Vollständige Referenzgraphen, Kandidatenmatrizen, XML | Nicht Bestandteil der studentischen Antwort |
| Technische Exception mit Eingabedaten | Bereinigter Fehlercode und verständliche Meldung |

Vollständige interne Diagnoseansichten dürfen nur über bereits geeignete, ausdrücklich geprüfte Berechtigungen zugänglich sein. Falls solche Berechtigungen noch nicht bestehen, entsteht in diesem Paket kein neuer frei zugänglicher Rohdatenendpunkt.

### 5. Vorhandene Sidebar ergänzen

Die bestehende Verlaufsliste und Schrittdarstellung bleiben der Einstieg. Die Ergebnisansicht zeigt in dieser Reihenfolge:

1. Ausgewertete Modellversion und technischer Laufzustand.
2. Fachlicher Ergebnisstatus: vollständig, teilweise oder nicht verfügbar.
3. Entscheidung zur maßgeblichen Referenz beziehungsweise Hinweis auf offene Alternativen.
4. Befunde mit betroffenen Abgabeelementen.
5. Offene Zuordnungen und technische Einschränkungen.

Fachliche Befundcodes erhalten kurze feste Anzeigetexte, etwa „Abweichende Zugehörigkeit“ oder „Zuordnung nicht eindeutig“. Das ist eine Ergebnisdarstellung; didaktisch gestufte Hinweise und automatische Noten bleiben spätere Funktionen.

Bei offener Referenzauswahl werden widersprüchliche alternative Befunde nicht zu einer gemeinsamen Fehlerliste vermischt. Sie bleiben referenzbezogen beziehungsweise die Anzeige beschränkt sich auf eindeutig gemeinsam geltende Aussagen.

### 6. Versionsbezug beachten

Die Sidebar nennt immer den analysierten Stand. Ist das aktuelle Modell inzwischen geändert, erscheint dieser Unterschied sichtbar. Originalzell-IDs dürfen nicht ungeprüft auf einen anderen Stand angewendet werden.

Wenn eine vorhandene Navigation zu Elementen verwendet wird, darf sie nur tatsächlich vorhandene Abgabeelemente des passenden Stands adressieren. Fehlende Elemente erhalten eine Ergebniszeile und gegebenenfalls einen belegten Besitzerbezug; es werden keine Geisterelemente in den Canvas eingefügt. Neue automatische Overlays oder Schreibzugriffe auf die Feedbacksammlung sind für diesen Schritt nicht erforderlich.

## Fehlerverhalten

- Fehlende Leseberechtigung wird durch die bestehenden API-Zugriffsregeln abgefangen.
- Ein ungültiges Gesamtartefakt ergibt einen technischen Ergebnisfehler, keine leere fachliche Erfolgsanzeige.
- Wenn Dagu nach einem bereits gespeicherten Abschluss nicht erreichbar ist, bleibt das gespeicherte fachliche Ergebnis lesbar.
- Wenn Dagu vor einem Abschluss nicht erreichbar ist, bleibt der Status ausdrücklich unklar; die API erfindet keinen Abschluss.
- Eine neue Bearbeitung der Abgabe verändert kein historisches Auswertungsergebnis.

## Erfüllungskriterien

- [ ] Der Nutzer sieht das Ergebnis ausschließlich zur tatsächlich ausgewerteten Modellversion.
- [ ] Fachliche Vollständigkeit und technischer Laufstatus werden getrennt dargestellt.
- [ ] Ein vorhandenes Teilergebnis bleibt trotz fehlgeschlagenem Zweig zugänglich.
- [ ] Ein Abschluss wird nur aus einem gültigen, ausdrücklich benannten Gesamtartefakt übernommen.
- [ ] Referenzinhalte sind auch in Schritt-JSON, Zusammenfassungen und Fehlermeldungen gemäß Offenlegungsregel geschützt.
- [ ] Ungeklärte Zuordnungen erscheinen als ungeklärt und nicht pauschal als falsch oder fehlend.
- [ ] Das gespeicherte abgeschlossene Ergebnis bleibt unabhängig von der späteren Logverfügbarkeit darstellbar.
- [ ] Die initiale Anzeige weist keine automatisch erfundene Note aus und verändert keine Modellelemente.

**Aktuelle Verifikation:** Ausschließlich statische Durchsicht der Änderungen und Schnittstellen. Keine Tests erstellen, erweitern oder ausführen; keine manuellen Modell-/Containerläufe, Builds, Benchmarks, Lint- oder Syntaxprüfungen. Die Kriterien beschreiben Sollverhalten und sind derzeit kein Auftrag zur Ausführung.

## Ergebnis nach diesem Paket

Die initiale Pipeline ist aus der Anwendung heraus nutzbar: gespeicherte Abgabe starten, Zwischenstände nachvollziehen und ein quellenbezogenes, gegebenenfalls eingeschränktes Vergleichsergebnis erhalten. Bewertung, didaktische Hinweise und MMU-Matching können anschließend auf den vorhandenen Verträgen aufbauen.
