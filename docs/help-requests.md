# Hilfe im Lernpfad

Das Lernpfad-Feature „Hilfe anfordern“ aktiviert den Button „Ich brauche Hilfe“.
Beim Klick speichert der Editor einen Modell-Checkpoint und legt eine Hilfe-Anfrage
mit Verweis auf genau diese Version an.

Der Ablauf verwendet drei reguläre, veröffentlichte Fragebögen:

1. Problembezug: Aufgabenstellung/Modell, Bedienung des Tools oder Anderes mit
   bedingtem Pflicht-Freitextfeld.
2. Gefühlte Dauer des Stillstands und gewünschte Art der Unterstützung.
3. Gewählte nächste Hilfequelle: Vorlesungsfolien, Lehrkraft, andere Studierende
   beziehungsweise Kolleginnen/Kollegen oder eine selbst gewählte Hilfequelle.

Bei Aufgabenstellung/Modell liegt zwischen den ersten beiden Fragebögen ein
Markierungsmodus. Er zeigt den gespeicherten Checkpoint. Modellelemente und
Verbindungen werden durch Anklicken markiert; im Aufgabentext werden ausgewählte
Textstellen über „Textstelle markieren“ hinzugefügt. Markierungen verändern weder
das Modell noch den Aufgabentext. Mindestens eine Markierung ist erforderlich.

Die Definitionen liegen in
`api/src/modeling_api/db/initial_data/help_questionnaires.json`. Der API-Start
erzeugt die Fragebögen und ihre ersten Releases idempotent mit stabilen IDs;
bestehende Fragebögen werden nicht überschrieben. Eigene Änderungen sollten die
Fragenamen und die drei Problemkategorien erhalten, da sie den Ablauf steuern.

`learning_path_help_requests` hält Modellversion, Ablaufstatus, Markierungen und
die Verweise unter `surveySessions`. Die Antworten selbst liegen in den regulären
`survey_sessions` und beziehen sich auf das jeweils verwendete Fragebogen-Release.
Textreferenzen speichern ProseMirror-Positionen und den ausgewählten Text; ihr
Bezug ist die Aufgabenstellung beziehungsweise deren `taskEditSnapshot` der
gespeicherten Modellversion.

Offene Abläufe werden nach einem Neuladen fortgesetzt. „Abbrechen“ beendet den
Ablauf und erhält die bereits gespeicherten Angaben. Die Wahl einer Hilfequelle
speichert eine Absicht und zeigt einen passenden nächsten Schritt; sie verschickt
keine Nachrichten. Eine automatische Überprüfung wird derzeit nicht angeboten.
