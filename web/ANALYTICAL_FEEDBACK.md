# Analytical Feedback

## Datenfluss und Zugriff

`generate_analytical_feedback` veröffentlicht weiterhin sein unverändertes stdout
als `analysis-result.json` (`workflow-result/v1`, darunter
`result.schema: analysis-feedback/v1`). Der vorhandene autorisierte Abruf
`GET /api/v1/evaluations/{evaluationId}` liest das Artefakt des Referenz-Unterlaufs,
ersatzweise dessen stdout. Die API prüft die Hülle und entpackt `result` für die
Auswertungsschritte. Besitzerprüfung und die Beschränkung analytischer Daten auf
Moderatoren/Administratoren bleiben bestehen. Das Frontend verwendet keine
internen Datei-, Kubernetes- oder Workspace-Pfade.

`evaluationService.getAnalysis(evaluationId, referenceKey)` bietet den gezielten
Adapterzugriff. Die Auswertungsseitenleiste verwendet denselben Adapter direkt
auf dem bereits geladenen Detail, um einen zweiten Abruf zu vermeiden. Der
Referenzschlüssel stammt aus dem analytischen Auswertungsschritt und ist über
die Musterlösungsauswahl wechselbar.

`analysisFeedback.ts` validiert Schema, vorläufigen Status, Auswertungskennung,
Referenzpaar, Hashformat, Graphzugehörigkeit, Vergleichshash und bestehende
Zuordnungspaare, Original-IDs und Objektarten,
vollständige/eindeutige Annotationen, Referenzgegenstücke, Abhängigkeiten,
Hinweisziele und Zähler. IDs stammen aus den beiden gespeicherten
`graph-result/v1`-Ergebnissen derselben Auswertung. Der Index ist
`Map<target.kind, Map<target.id, annotation>>`. Hashes werden auf ihr Format,
nicht kryptografisch erneut auf den vollständigen Workflowinhalt geprüft.
Fehlende Graphen, ungültige Daten oder zurückgehaltene Analyse führen zu einer
sichtbaren Meldung und keinen Markierungen.

## Anzeige

Die Serviceansicht der Auswertungsseitenleiste enthält vier Erkennungsquoten,
eine Objektauswahl und sämtliche vorhandenen Einzelprüfungen, Zuordnungsgründe,
Referenz-IDs, Abhängigkeiten, lokale Kinder-/Verbindungszähler und Hinweise.
Semantische Einzelmethoden und Scores werden nicht angezeigt. Original-IDs
stehen auch bei Beschriftungen mit gleichem Namen zur Verfügung. Diagrammauswahl
und Detailanzeige sind gekoppelt. Die Studierendenansicht erhält durch diese
Änderung keine zusätzlichen analytischen Berechtigungen.

| Anzeigestatus | Symbol | Grundlage |
| --- | --- | --- |
| Vorläufig erkannt | Dezentes Häkchen | Vorläufige Zuordnung ohne festgestellte strukturelle Abweichung oder offene Einzelprüfung |
| Strukturelle Abweichung | Warnsymbol | Individuelle Besitzer-, Containment-, Endpunkt-, Richtungs- oder Verbindungstypprüfung ist `violated`/`different` |
| Ungeklärt | Fragezeichen | Ungeklärte Zuordnung/Prüfung, Mehrdeutigkeit oder Verbindungsgruppenbefund |
| Nicht ausgewertet | Informationssymbol | Keine vorläufige Zuordnung und kein stärkerer Befund |

Alle Einzelstatus bleiben erhalten. `provisional` bleibt auch neben einer
Warnung sichtbar. `label.different` und `compatible_type_difference` sind
Abweichungshinweise und werden allein nicht als bewiesene Strukturfehler
behandelt. Bei `connectionScope: endpoint_group` sind Richtung/Verbindungstyp
ausdrücklich Gruppenbefunde und erzeugen keinen individuellen Fehlernachweis.

Referenzhinweise erhalten ein zusätzliches Fragezeichen am angegebenen
Abgabeobjekt. Ist dieses nicht gerendert, wird der nächste gerenderte Parent
verwendet; ohne sichtbaren Parent erscheint ein Modellhinweis. Nicht
identifizierte Referenzobjekte werden nicht als bestätigt fehlend bezeichnet.

Overlays sind lokale Laufzeitobjekte. Sie ändern weder XML noch Modellstil oder
Undo-Historie. Beim Wechsel der Auswertung, Referenz oder Ansicht und beim
Schließen werden nur die eigenen Overlays entfernt. Stimmt das aktuelle
Diagramm-XML nicht mit dem gespeicherten Abgabestand überein, bleiben die
Markierungen ausgeblendet; die Details werden als historische Befunde erklärt.

## Klassifikation und Kennzahlen

Im Sprach-Editor unter Evaluation → Recognition categories können native
Elementtypen allgemein `nodes`, `attributes` oder `other` zugeordnet werden.
Die Sprachdefinition speichert dies unter
`evaluation.elementCategories: Record<nativeType, category>`. Nicht
klassifizierte Typen bleiben `other`; aus Bezeichnungen oder verschachtelten
Strukturcontainern werden keine Attribute erraten. Verbindungen klassifiziert
der vorhandene Workflow selbst.

Die API überträgt diese Metadaten inklusive Sprach-/Versionskennung nach
`comparisonConfig.graphMatching.elementCategories` des eingefrorenen
Auswertungseingangs. Explizit übergebene Vergleichskonfigurationen behalten
Vorrang. Graph- und Synonym-Matchingcode bleiben unverändert. Die Konfiguration
gilt für neue Auswertungen; bestehende Artefakte werden nicht umgerechnet.

Jede Kategorie zeigt Zähler, Nenner, Prozentwert und Auswertungsstatus.
`null` erscheint als „nicht bestimmbar“. Fehlende Kategorien erhalten unbekannte
Zähler/Nenner und `not_evaluated`, keine erfundene Quote. Unterstützte Status
sind `provisional`, `partial`, `not_evaluated` und `not_applicable`; unbekannte
Status bleiben als technische Werte lesbar.

## Zentrale Hinweis-Codes

Texte und Anzeigesymbole sind in `analysisFeedback.ts` zugeordnet. Parameter
bleiben als strukturierte Details lesbar; unbekannte Codes erscheinen als
„Technischer Hinweis: CODE“ mit ihren Parametern.

| Code | Bedeutung |
| --- | --- |
| `identity.unresolved`, `identity.ambiguous` | Identität ungeklärt bzw. mehrere Kandidaten |
| `label.different` | Abweichende Beschriftung |
| `type.compatible_difference` | Anderer konkreter Typ innerhalb einer Vergleichsgruppe |
| `owner.violated`, `owner.different`, `owner.unresolved` | Besitzer verletzt, abweichend oder ungeklärt |
| `containment.violated` | Zugehörigkeit verletzt |
| `connection.endpoints_different` | Individuell abweichende Endpunkte |
| `connection.group_difference` | Gruppenbefund; Dimensionen, IDs und Gruppenzähler bleiben sichtbar |
| `children.unresolved_reference`, `connections.unresolved_reference` | Offene Referenzobjekte im lokalen Kontext |
| `children.unresolved_submission`, `connections.unresolved_submission` | Offene Abgabeobjekte; nicht bestätigt zusätzlich |
| `children.mapped_from_other_target`, `connections.mapped_from_other_target` | Vorläufig einem anderen Kontext zugeordnet |
| `children.outside_target`, `connections.outside_target` | Erkannte Objekte außerhalb des Anzeigeziels |
| `reference.unresolved` | Referenzobjekt nicht identifiziert; Ziel ist Parent oder Modell |

## Lokale Verifikation und Grenzen

Adapter und Darstellungslogik wurden lokal mit Mock-Berichten und Original-IDs
aus den gespeicherten Modellen Baseline, M03 und M06b geprüft. Dies umfasst
68 adressierbare Objekte, Struktur- und Gruppenbefunde, Referenzhinweise,
fehlende Kategorien, ungültige Daten und die gezielte Overlay-Bereinigung.
Frontend-Testdateien sind nicht Bestandteil der Änderung. Eine gerenderte
Browseroberfläche und echte Workflowberichte wurden damit nicht verifiziert.

Das Lesen gespeicherter Dagu-Läufe über den konfigurierten MCP war bei der
Implementierung durch `permission denied` beim Auflisten von Laufverzeichnissen
blockiert. Deshalb wurden keine echten Analyseartefakte aus diesen Läufen
verifiziert. Es wurde keine vollständige Pipeline gestartet und kein
Dagu-Ersatzdienst verwendet.
