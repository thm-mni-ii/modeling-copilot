# Feedback jederzeit aufrufen und in der Modellhistorie zuordnen

**Ziel.** Bereits vorhandenes Feedback bleibt unabhängig von späteren Modelländerungen aufrufbar. Die Timeline zeigt, zu welcher gespeicherten Modellversion eine Auswertung gestartet wurde, wann dies geschah und welchen Status der Lauf hat. Von dort lässt sich das zugehörige Feedback zusammen mit dem damaligen Modell ansehen.

**Verbindliche Abgrenzung.** Start, Berechnung, Feedbackarten, Rollenfreigaben, Hilfeanfragen und Abschlussprüfung funktionieren wie bisher. Neben Abruf, Navigation und historischer Darstellung bleiben im aktuellen Editor Markierungen für fachlich unveränderte Objekte und ihre Abhängigkeiten erhalten. Dies wendet vorhandenes Feedback weiter an und führt keine neue Auswertung durch.

## Bedienung

1. In der bestehenden Auswertungsleiste lassen sich vorhandene Auswertungen auch nach Änderungen am Modell öffnen. Das Feedback bleibt seinem ursprünglichen Lauf und Modellstand zugeordnet. Die Detailansicht zeigt diese Zuordnung unabhängig davon, ob sich der Entwurf verändert hat; eine fachliche Gleichheitsprüfung ist dafür nicht nötig. **„Modellstand ansehen“** öffnet die Timeline mit der referenzierten Version und genau diesem Lauf. Der Einstieg startet keine Auswertung und speichert den aktuellen Entwurf nicht.
2. Die Timeline öffnet sich bei diesem Einstieg mit aktivierter Option **„Feedback einblenden“**. Links erscheint die schreibgeschützte Vorschau des damaligen Modells, rechts das bereits für die Rolle verfügbare Feedback. Auf schmalen Bildschirmen kann zwischen Modell und Feedback gewechselt werden, ohne die Auswahl zu verlieren. Vorhandene Objektbezüge innerhalb des historischen Feedbacks beziehen sich ausschließlich auf die Vorschau.
3. Jeder Auswertungslauf erhält einen eigenen beschrifteten, per Tastatur erreichbaren Punkt in der Versionsleiste. Mehrere Läufe derselben Version erscheinen als getrennte Stände mit identischer Modellvorschau. Sie referenzieren weiterhin dieselbe gespeicherte Version; es entstehen keine Datenbankduplikate. Der gewählte Punkt bestimmt unmittelbar den angezeigten Lauf. Eine zusätzliche Laufnavigation unter der Leiste entfällt. Startzeit und vorhandener Status unterscheiden die Läufe. Auch laufende, fehlgeschlagene, abgebrochene oder im Status unklare Läufe sind zugeordnet; ein Marker behauptet keinen erfolgreichen Abschluss. Ohne verfügbares Feedback erscheint der bestehende Status beziehungsweise ein Hinweis auf das fehlende Ergebnis.
4. Beim Bewegen des Reglers wechseln Vorschau und zugeordnetes Feedback gemeinsam. Feedback erscheint nur an der exakt referenzierten Version. Zwischenstände einzelner Patches oder Aufgabenänderungen erhalten durch ein gleich aussehendes Diagramm keine Auswertung. An Positionen ohne zugeordneten Lauf steht **„Für diesen Stand gibt es keine Auswertung“**. Von dort kann eine frühere Auswertungsmarkierung ausgewählt werden.
5. **„Zurück zum Editor“** schließt die historische Ansicht. Der aktuelle Entwurf einschließlich ungespeicherter Änderungen bleibt erhalten. Die Auswahl innerhalb des Dialogs bleibt lokal und verändert die Auswahl der Auswertung in der bestehenden Editorleiste nicht. Beim normalen Öffnen der Timeline kann „Feedback einblenden“ eingeschaltet werden. Die bestehenden Funktionen zum Wiederherstellen und Verzweigen bleiben im normalen Timeline-Modus; der Einstieg aus einem Feedback ist eine reine Leseansicht.

## Zuordnung und technische Grundlage

- **Identität und Zeit.** Modell-ID, Versions-ID und Auswertungs-ID bestimmen die Zuordnung. Der Marker sitzt an der gespeicherten Modellversion, die Startzeit wird am Lauf angezeigt. Die Timeline bleibt ein Verlauf von Modellständen und wird nicht zu einer nach Auswertungszeiten skalierten Zeitachse. Modellversion und Auswertung können unterschiedliche Zeitpunkte haben; für „Auswertung gestartet“ zählt die Startzeit des Laufs. Eine Abschlusszeit wird nur angezeigt, wenn sie tatsächlich vorliegt.
- **Checkpoints und Releases.** Bei mehreren Patches gehört der Marker an den Endstand des Checkpoints. Für eine ausgewertete Version ohne eigene sichtbare Position wird eine explizite Versionsposition ergänzt. Das gilt auch, wenn die bestehende Timeline den letzten Patch vor einem Release ausblendet. Die ursprüngliche Versions-ID bleibt erhalten; das Feedback wird nicht einer anderen Version zugeschrieben. Für diese Position wird die gespeicherte Version direkt als Vorschau geladen.
- **Navigation und Laden.** Der Dialog erhält Zielversion und Auswertungs-ID. Alle Seiten der Auswertungsliste müssen erreichbar sein. Detailfeedback wird erst für den ausgewählten Lauf über die bestehenden rollenabhängigen Abrufe geladen. Verspätete Antworten dürfen nach einem Positions- oder Laufwechsel kein unpassendes Feedback anzeigen. Beim Umschalten der Aufgabenhistorie bleibt ein ausgewähltes Auswertungsziel anhand seiner IDs erhalten.
- **Getrennte Vorschau.** Die vorhandene Modellvorschau verwendet eine eigene Zeichenfläche. Die historische Feedbackansicht muss deren Diagrammkontext verwenden, damit die Auswahl eines Objektbezugs nicht den aktuellen Editor anspricht. Navigieren und Betrachten verändern weder den Entwurf noch dessen Undo-Verlauf. Eine zusätzliche Übertragung historischer Markierungen auf den aktuellen Entwurf ist nicht vorgesehen.
- **Vorhandene Feedbackformate und Rechte.** Die historische Ansicht verwendet die vorhandenen Inhalte und Rollenfreigaben. Dazu gehören auch die bereits freigegebenen objektbezogenen Hilfeformate für Studierende. Analytische Service-Befunde bleiben auf die bisher berechtigten Rollen beschränkt. Die bestehenden Darstellungen einschließlich technischer Laufdetails und Exporte werden wiederverwendet. Die Erweiterung führt keine neuen Feedbackarten oder neuen fachlichen Bewertungen ein.
- **Fehlende Daten.** Ist der Modellstand nicht verfügbar, wird dies getrennt vom Feedback angezeigt; noch abrufbares Feedback bleibt lesbar. Fehlt das Ergebnis eines Laufs, bleiben dessen verfügbare Kennung, Versionszuordnung, Startzeit und Status sichtbar. Die Oberfläche erfindet weder Feedback noch historische Bewertungskriterien.

## Festgelegte Datenbasis

### Weitergeltung beim Bearbeiten

- Die Studierenden- und die analytische Ansicht prüfen Objektbezüge gegen den tatsächlich ausgewerteten Modellstand. Verschieben, Größenänderungen und rein grafische Gestaltung entwerten diese Bezüge nicht.
- Umbenennen, Löschen, Typänderungen, andere Eltern oder geänderte Verbindungsendpunkte entwerten die betroffenen Markierungen. Kinder, angrenzende Verbindungen, gleichnamige Vergleichskandidaten und veröffentlichte analytische Abhängigkeiten werden dabei berücksichtigt. Unabhängige Objekte behalten ihre Markierungen.
- Modellweite Fehlstellen- und Vollständigkeitshinweise werden nach fachlichen Änderungen nicht als aktuelle Diagrammmarkierungen weitergeführt. Die ursprünglichen Texte und Ergebniswerte bleiben zum ausgewerteten Stand lesbar.
- Entspricht ein Objekt einschließlich seiner Abhängigkeiten nach Undo wieder dem ausgewerteten Stand, können seine Markierungen erneut erscheinen. Neue Objekt-IDs erben kein Feedback durch denselben Namen.

### Ergebnisabruf

1. **Vorhandene Laufdaten.** Laufdaten werden nicht gelöscht. Die historische Ansicht verwendet die vorhandenen Abrufe und gespeicherten Ergebnisse. Es werden keine zusätzlichen Archive, Ergebnisduplikate oder neuen Speicherprozesse eingeführt. Ein Lauf muss für die Anzeige nicht reproduziert oder erneut ausgeführt werden.
2. **Gespeichertes Ergebnis.** Die historische Ansicht zeigt das Ergebnis und Feedback des ausgewählten Laufs. Aktuelle Lernpfadschwellen werden dabei nicht angewendet; eine neue Abgabebereitschaft wird nicht berechnet. Änderungen früherer Schwellenwerte müssen nicht rekonstruiert werden. Die bestehende Abschlussprüfung im Editor bleibt unverändert.

## Umsetzung und Abnahme

Die Umsetzung beschränkt sich auf die Verbindung zwischen Auswertungsleiste und Timeline, die Zuordnung der Marker und die historische Feedbackdarstellung auf Grundlage der vorhandenen Laufdaten.

| Fall | Erwartetes Ergebnis |
| --- | --- |
| Nach einer Auswertung Elemente umbenennen, verschieben oder löschen; Änderungen ungespeichert lassen | Der ursprüngliche Lauf und sein Feedback bleiben aufrufbar. Die Timeline zeigt den zugehörigen gespeicherten Modellstand. Nach dem Schließen sind Entwurf und Undo-Verlauf unverändert. |
| Zwei Läufe auf derselben Version; später einen weiteren Lauf starten | Jeder Lauf erhält einen eigenen Punkt in der Versionsleiste mit derselben gespeicherten Modellreferenz. Es gibt keine separate Laufnavigation und keine zusätzliche Speicherung. Der gezielte Einstieg wählt genau den angeklickten Lauf. |
| Checkpoint mit mehreren Patches, Checkpoint ohne Patch und ausgeblendeter Endstand vor einem Release | Jeder Lauf erreicht seine ursprüngliche Version. Ein Marker steht nicht versehentlich auf einem Zwischenpatch oder einem anderen Release. |
| Zwischen Auswertungsmarkern navigieren oder Aufgabenhistorie einblenden | Modell und Feedback bleiben richtig zugeordnet. Ein Stand ohne Lauf zeigt kein fremdes Feedback; ein ausgewähltes Auswertungsziel bleibt beim Umschalten erhalten. |
| Älteren Lauf außerhalb der ersten Ergebnisseite öffnen; schnell zwischen Läufen wechseln | Der Lauf ist erreichbar. Späte Antworten überschreiben die aktuelle Auswahl nicht. |
| Lauf ist noch aktiv, fehlgeschlagen, abgebrochen oder ohne abrufbares Ergebnis | Die verfügbaren Laufangaben und der Status werden gezeigt. Der Marker stellt keinen erfolgreichen Abschluss dar. |
| Historischen Objektbezug auswählen | Ausschließlich die Vorschau wird angesprochen; der aktuelle Editor bleibt unverändert. |
| Modellversion fehlt, Feedback ist noch vorhanden | Das Feedback bleibt lesbar; die fehlende Modellvorschau wird ausdrücklich benannt. |
| Als Studentin oder Service-Rolle öffnen | Es erscheinen dieselben für die jeweilige Rolle freigegebenen Feedbackinhalte wie im bestehenden Ablauf. |

## Grundlage der Prüfung im Repository

- [Start einer Auswertung und Abschlussprüfung](../web/src/views/ViewModeling.vue) und [serverseitige Abgabeentscheidung](../api/src/modeling_api/services/learning_paths.py)
- [Zusammensetzung der Modellhistorie](../web/src/utils/modelTimeline.ts), [Timeline-Dialog](../web/src/components/modeling/versions/ModelTimelineDialog.vue) und [Modellvorschau](../web/src/components/modeling/versions/ModelSnapshotPreview.vue)
- [Studierenden- und Serviceansicht](../web/src/components/modeling/sidebars/EvaluationSidebar.vue), [vorhandene Hilfeformate](../web/src/components/feedback/FeedbackView.vue) und [Diagrammkontext](../web/src/composables/useGraphContext.ts)
- [Speicherung und Bereitstellung der Auswertung](../api/src/modeling_api/services/evaluations.py)
