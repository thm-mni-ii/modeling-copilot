# Technische Validierung der Testdaten

Aktuelle Testdaten:
[data/Test Cases](../../../../../data/Test%20Cases/).
Archivabgleich und Bereinigungsumfang:
[archive-audit.json](archive-audit.json).
Technische Erwartungen der zwölf Modelle:
[unique-models.json](unique-models.json).

Der Archivabgleich bestätigte zwölf unterschiedliche XML-Inhalte in 112
vollständigen Snapshots. Die Modelle wurden mit neutralen IDs und Texten
übernommen. Knoten-Typen, Verbindungen und Enthaltenseinsstruktur blieben
gegenüber den Originalgraphen erhalten; alle zwölf Modelle sind vollständig
auflösbar und erzeugen keine Parserdiagnosen. Drei vollständige Sprachversionen
stimmen mit Archiv und Repository-Definitionen überein.

Die früheren Original-Versions-IDs und das Manifest der 270 Archivversionen
werden aus Datenschutzgründen nicht mehr veröffentlicht. Der alte Bericht
`mongo-20261104-155523.json` wurde durch den aggregierten Archivabgleich ersetzt.

Vor der Bereinigung wurden 21 vollständige lokale Serviceabläufe einschließlich
aller nachgelagerten Dienste erfolgreich ausgeführt. Das war keine Live-Prüfung
des Dagu-/Kubernetes-Schedulings und kein fachliches Grading. Einzelergebnisse:
[workflow-cases.json](workflow-cases.json).
Der Datenordner enthält ausschließlich Modelle, Sprachen und Aufgaben.
Runner und Ablaufkonfiguration wurden entfernt; eigene Tests organisieren ihre
Eingaben und Erwartungen selbst.
Die Matching-/Feedback-Algorithmen sind weiter Platzhalter.
Historische Infrastrukturprüfungen stehen in [local-workflow.md](local-workflow.md)
und beziehen sich auf den dort beschriebenen früheren Entwicklungsstand.
