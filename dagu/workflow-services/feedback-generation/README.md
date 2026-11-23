# feedback-generation

Serviceversion `4.9.2`, Image `v39`, Ausgabe `feedback-report/v4` in
`workflow-result/v1`.

Der Dienst verlangt `WORKFLOW_EVALUATION_ID`, `REFERENCE_KEY` und
`ANALYSIS_INPUT_PATH`. Er validiert das konkrete Analyseartefakt gegen Snapshot,
Referenzpaar, Vergleich, Pfad und Hash.

## Feedbacktypen

Welches Feedback erzeugt wird, steht im eingefrorenen `evaluation-input/v1` unter
`feedbackRequest`:

```json
"feedbackRequest": {"types": ["recognition"], "context": {}}
```

Fehlt das Feld, gilt genau dieser Default. `types` ist eine nicht leere Liste
eindeutiger, bekannter Typnamen; unbekannte Typen brechen den Schritt ab.
Der Bericht enthält unter `requested` die angeforderten Typen und unter `feedback`
je Typ genau einen Eintrag `{"type": …, …}` – nichts darüber hinaus. Neue Typen
werden als Builder in `BUILDERS` (`src/main.py`) ergänzt.

Jeder Hilfetyp hat eine feste Freigabestufe (`LEVELS` in `src/help_feedback.py`);
Lehrende stellen sie nicht ein.

| Typ | Stufe | Inhalt |
|---|---|---|
| `recognition` | – | `recognition` des Analyseartefakts unverändert (Erkennungsübersicht für Auswertung und Aufgabenabschluss) |
| `help.clarify` | Diagnose | je markiertem Objekt `identity`, `verdict` und `score` (Vollständigkeit des Objekts in Prozent: Beschriftung erkannt samt Textähnlichkeit, Typ korrekt/abweichend, untergeordnete Elemente und ein-/ausgehende Verbindungen als „vorhanden von erwartet“; bei nicht zuordenbarer Beschriftung ein Hinweis zum Konkretisieren); die UI markiert die Objekte im Diagramm als korrekt, abweichend oder nicht zuordenbar |
| `help.next_step` | Beschriftungen (nur fehlende Kinder) | genau ein lokaler Hinweis: (1) markiertes Element: Beschriftung zuordenbar (erkannt gen?gt), Typ, Zuordnung, dann vorhandene verschachtelte Elemente einschlie?lich nicht zuordenbarer/?berfl?ssiger Kinder, falsch zugeordnete und fehlende Kinder; strukturelle Container werden ?bersprungen, Verbindungen z?hlen nie als fehlende Kinder. (2) Vorhandene eingehende Verbindungen: Zuordenbarkeit, Endpunkte/Richtung, danach fehlende eingehende Verbindungen. (3) Ebenso ausgehende/ungerichtete Verbindungen. (4) Erst danach die Typen aller angeschlossenen Verbindungen. Keine transitive Pr?fung von Nachbarelementen und keine Aufforderung, benannte Nachbarelemente anzulegen; fehlende Verbindungen werden ohne Musterl?sungsnamen oder Typvorgabe benannt. Verschachtelte Elemente setzen beim Besitzer fort; markierte Verbindungen pr?fen nur sich selbst (Struktur vor Typ). Ohne Befund: kein ?nderungsbedarf an den ?berpr?ften Objekten. |
| `help.example` | Beschriftungen | Strukturmuster je markiertem Objekt (`pattern.expected`): Ausschnitt der Musterlösung um das Gegenstück mit Nachbarn und deren untergeordneten Elementen; erkannte Elemente unverändert mit der eigenen Bezeichnung, übrige hellgrau, gestrichelt und kursiv als Platzhalter mit ihrem Elementtyp. Im Katalog liegen Muster einmal je Element unter `patterns` |
| `help.check` | Diagnose | ohne Markierung: Gesamterkennung (`overview` und `recognition` des Analyseartefakts; die UI zeigt dieselben Balken wie beim Aufgabenabschluss) und alle Abgabeobjekte, die sie als eindeutig erkannt zählt; die UI setzt an ihnen im Diagramm einen grünen Haken |
| `help.solution` | Beschriftungen | je markiertem Objekt die vollständige Soll-Konstellation: korrekt, vermutlich überflüssig (keine Entsprechung) oder alle Änderungen inkl. Anzahlen und Musterlösungsbeschriftungen, dazu `example` mit dem zugeordneten Element der Musterlösung: Art, Beschriftung, Typname, `xml` (Ein-Schritt-Umgebung als eigenständiges maxGraph-XML aus der Musterlösung: bei Verbindungen beide Endelemente, bei Elementen alles Verschachtelte samt strukturierter Container und alle Verbindungen, deren anderes Ende offen bleibt: schematisch auf der Seite zum verborgenen Element, parallel und gleichmäßig verteilt) und `definition` (Sprachdefinition laut `definition.path`) als Rückfall |
| `help.catalog` | – | nur Analyseansicht: je Abgabeobjekt die Einträge aller fünf Hilfetypen, als wäre nur dieses Objekt markiert; ohne `context`. Die API fordert ihn bei Läufen von Administrierenden/Moderierenden an und gibt ihn nie an Lernende weiter |

`help.next_step` nennt den Hinweis `child.likely_elsewhere` nur, wenn die Beschriftung in der Abgabe genau einmal vorkommt, genau ein offenes Gegenstück der Musterlösung die Textschwelle erreicht und dessen Besitzer bereits als anderes Abgabeelement erkannt ist. Eine Teilerkennung (`partial`) löst ihn nicht aus, weil ihr Besitzer unbelegt ist.

Hilfetypen außer `help.check` erwarten in `context`: `markedIds` (1–200 Zellen-IDs der Abgabe) und
optional `previousIssueKeys` (markiert wiederholte Hinweise über `focus.repeated`).
Jeder Hilfeeintrag enthält zusätzlich `overview` (Gesamterkennung). Alle Texte sind
modellierungssprachneutral; fachliche Begriffe stammen nur aus Aufgabe, Abgabe,
Musterlösung (Stufe Beschriftungen) und Sprachdefinition (Typnamen).
Die API setzt `feedbackRequest` beim Start aus einer abgeschlossenen Hilfe-Anfrage
(`helpRequestId`) und gibt Hilfeeinträge über eine Allowlist an Lernende weiter.

`recognition` enthält dynamische Gruppen-/Typzeilen, Gesamtzahlen und separat nicht zugeordnete
Abgabeobjekte. Details und Statusdefinitionen stehen im
[Analysevertrag](../analytical-feedback/README.md); das gemeinsame
[JSON-Schema](../analytical-feedback/schemas/output.schema.json) definiert
`$defs.feedbackReportV4`. Die UI zeigt diese veröffentlichten Werte an, ohne aus
Zuordnungen neue Erkennungszahlen zu berechnen. Die Quote ist keine
Korrektheitsquote und keine Note; `assessmentAvailable` bleibt `false`.

Die vollständige kompakte Ausgabe bleibt eine JSON-Zeile auf stdout und wird von
Dagu als `feedback-result.json` gespeichert.

Gespeicherte v2-/v3-Berichte (Erkennung direkt unter `recognition`) werden von API und
UI weiterhin gelesen. v1-Artefakte bleiben als historische technische Ergebnisse
verfügbar, werden aber nicht als aktuelle `recognition` angezeigt. Neue Berichte
aus alten Analysen oder ohne Analysepfad erfordern eine Neuberechnung.
