# analytical-feedback

Serviceversion `1.3.0`, Vertragsrevision `1.3` mit Identitäts- und Positionsfakten,
Image `v6`. Vergleiche mit Matcher-Fakten `1.1` verwenden den reinen Faktenpfad;
Fakten `1.0` werden weiterhin als Revision `1.2`, Vergleiche ohne Fakten als
Revision `1.1` projiziert. Gespeicherte frühere Revisionen bleiben lesbar.

`annotations[].identity` zeigt `uniquely_supported`, `supported` oder `unresolved`
mit den positiven, negativen und offenen Evidenzmethoden. Erkennung und
Eigenschaftskorrektheit werden getrennt dargestellt. Die Kindcheckliste zeigt
korrekt enthaltene Kinder als `matched/expected`, erkannte verschobene Kinder,
offene Gegenstücke und nachgewiesene Abwesenheit ohne doppelte Zählung.
Der neue Pfad übernimmt auch Beobachtungen und Relationsziele aus den
Matcher-Fakten; er führt keine eigenen Eigenschafts- oder Relationsprüfungen aus.
`targets` adressiert Child und beide beteiligten Parents. Eine gemeinsame
`findingId` verhindert doppelte Positionshinweise und Parent-Overlays.

Die Faktenrevisionen übernehmen `propertyFacts` des Matchers unverändert als `facts`
in `annotations`, `referenceHints` und Verbindungsgruppen. Jeder Fakt nennt seine
Original-IDs, Status und Beweisgrundlage. Der Feedbackdienst entscheidet keine
dieser Eigenschaften erneut. `checks` und kurze `fact.*`-Hinweise dienen als
Anzeigeprojektion; Gruppenbefunde behaupten keinen individuellen Fehler.
Die Validierung prüft die Fakten gegen den ursprünglichen Vergleich.

`consistency: "fully_consistent"` gilt ausschließlich für implementierte lokale
Eigenschaften unter einer vorläufigen Zuordnung: sämtliche zugehörigen Fakten
müssen `satisfied` oder `not_applicable` sein; Revision `1.3` verlangt zusätzlich
eine eindeutig gestützte Identität. Die Identitätsmethoden sind alternative
Begründungen, keine gemeinsam zu erfüllende Checkliste. Offene oder nicht durchgeführte
Prüfungen verhindern die Aussage. Sie bestätigt weder endgültige Identität noch
rekursive Korrektheit aller Kindbeschriftungen. Erfüllte Teilprüfungen bleiben
auch bei abweichendem oder ungeklärtem Gesamtstatus sichtbar.
Nachgewiesene Abwesenheit wird mit `reference.missing` und ihrer Beweisgrundlage
am bisherigen Anzeigeziel ausgegeben. Unmatched allein bleibt `reference.unresolved`.

Zwei gespeicherte, weiterhin lesbare Annotation-Ausschnitte der Revision `1.2`
(keine vollständigen Workflow-Envelopes):
[vollständig konsistente lokale Eigenschaften](examples/fully-consistent-local.json)
und [nachgewiesene Abweichungen bei gleichem Namen und Typ](examples/proven-deviations.json).

Der Dienst fasst einen vorhandenen Graphvergleich elementbezogen zusammen; er
trifft keine neuen Zuordnungen. Er validiert Snapshot, Graphen, Inventare,
Kandidaten, Vergleich und deren Hashketten. Eingabeauswahl und Ergebnisvertrag
stehen in `schemas/input.schema.json` und `schemas/output.schema.json`.

Die Ausgabe liegt als `workflow-result/v1` mit einem `analysis-feedback/v1`
unter `analysis/<referenceKey>/<analysisKey>.json` im Evaluation-Workspace.
Der inhaltsbasierte Schlüssel und `analysisHash` sichern eine unveränderliche,
bei identischem Inhalt wiederholbare Veröffentlichung.

`annotations` enthält genau einen Eintrag je Abgabeobjekt mit Original-ID,
vorläufigem Gegenstück, Entscheidungsregel, notwendigen Abhängigkeiten,
Prüfstatus und kurzen Hinweisen. Lokale Zähler unterscheiden erwartete,
erkannte und ungeklärte Kinder und Verbindungen. `referenceHints` adressiert
ungeklärte Referenzobjekte nach Möglichkeit am erkannten Parent oder Endpunkt,
ansonsten am Modell. `summary` enthält referenzbezogene Erkennungszahlen.
Der Kontext eines strukturellen Zwischencontainers ist ausdrücklich abgeleitet
und keine neue Zuordnung.

Alle Zuordnungen bleiben `provisional`. Eine Typabweichung innerhalb einer
Vergleichsgruppe ist keine automatische fachliche Fehlermeldung. Offene Elemente
oder Verbindungen gelten nicht als bestätigt fehlend oder zusätzlich;
Verbindungsgruppen begründen keine individuelle Verbindungsidentität.
Kandidatenmatrizen, Entscheidungsereignisse und vollständige Graphen verbleiben
in ihren ursprünglichen Workflow-Artefakten.

Der Dienst gibt das kompakte Envelope vorerst auf stdout aus. Dagu speichert es
als `analysis-result.json` und übergibt den Workspace-Pfad an
`feedback-generation`. Für die Übergabe akzeptiert der Workflow sowohl
`analysisPath` im Envelope als auch `path` in einer kompakten Statusausgabe;
ein fehlender oder ungültiger Pfad lässt den Übergabeschritt fehlschlagen.
Die API gibt die Analyse nur an Moderatoren und
Administratoren aus; die bestehende Besitzerprüfung der Auswertung gilt weiter.

## Gemeinsamer JSON-Vertrag und frühere Revision 1.1

Schema und Envelope bleiben `analysis-feedback/v1` beziehungsweise
`workflow-result/v1`; `contractVersion: "1.1"` kennzeichnet die Erweiterung.
Die Frontend- und Serviceadapter lesen weiterhin ältere v1-Artefakte.
Das [Ausgabeschema](schemas/output.schema.json) beschreibt die aktuelle Ausgabe.
Das [kompakte Beispiel](examples/containment-role.json) zeigt einen unabhängig
belegten Unterschied der Relationsrolle bei vorläufig zugeordneten Objekten.
Es ist eine Vertragsfixture, kein historisches Auswertungsergebnis.

| Feld | Bedeutung |
| --- | --- |
| `annotations[].target` | Original-ID, Objektart und Seite des Abgabeobjekts; keine Ersatz- oder Render-ID |
| `match` / `referenceId` | Ausschließlich die bestehende vorläufige Matcher-Zuordnung einschließlich Abhängigkeiten |
| `category` / `summary` | Kategorie sowie erkannte Referenzobjekte, Referenznenner, Prozent und Auswertungsstatus |
| `structuralContainers` | Separate Referenz-/Abgabezahlen und abgeleitete Kontexte; keine fachlichen Knoten |
| `owner` / `containment` | Nächster fachlicher Besitzer getrennt von unmittelbaren Parents mit Relationsrollen |
| `connection` | Beobachtete und zugeordnete Referenzverbindung: Original-ID, Source, Target, Richtung, konkreter Typ |
| `connectionGroups` / `groupIds` | Eigenständige Gruppenbefunde und Verweise; keine Übertragung auf individuelle Verbindungsprüfungen |
| `containmentRelations` / `relationIds` | Referenzkind, Referenzparent, Abgabekind, erwarteter Abgabeparent, beobachtete Parents/Rollen, Status und Begründung |
| `local` | Fachliche und direkte Kinder, angrenzende/eingehende/ausgehende/ungerichtete Verbindungen, ungeklärte Richtung sowie Containment-Prüfungen pro Relationsrolle |
| `referenceHints` | Ein separater Hinweis für jedes nicht individuell zugeordnete Referenzobjekt; Struktur-/Labelobjekte bleiben `not_evaluated` |
| `limitations` | Fehlende Kategoriendeklarationen beziehungsweise fehlende Besitzer-, Containment- oder Verbindungsgruppenprüfung |

Kategorien stammen aus `LanguageVersion.data.evaluation.elementCategories`, bei
älteren Snapshots ersatzweise aus den dort eingefrorenen
`comparisonConfig.graphMatching.elementCategories`. Der Sprach-/Versionsbezug
muss stimmen. Graphobjekte der deklarierten Art `connection` gehören zu
`connections`; strukturelle Objekte stehen separat. Unbekannte Objekte und
unaufgelöste Elementtypen bleiben `other`. Verschachtelung und Typnamen sind
keine Klassifikationsregeln. Die Nenner beziehen sich auf die gesamte jeweilige
Referenzkategorie; Prozentwerte bleiben ohne auswertbaren Eingang `null`.

`status` an Annotationen, Gruppen, Beziehungen und Hinweisen verwendet
`provisional`, `different`, `ambiguous`, `unresolved`, `not_evaluated` oder
`not_applicable`. `different` beschreibt den ausgewiesenen Befund, keine
endgültige Gesamtkorrektheit. Die kompatiblen `checks` behalten ihre bestehenden
Werte wie `equal`, `satisfied` und `violated`; `match.status` bleibt unverändert.
Hinweise enthalten immer `code`, `status`, `scope`, `parameters` und `targets`.
`targets` verwendet `{side: "reference" | "submission", id, kind}`. Die bisherigen
flachen Parameter und das Anzeigeziel `target` bleiben erhalten. Die Codes sind
im Schema geschlossen aufgezählt; Geltungsbereiche sind `element`, `relation`,
`group` und `model`. Codes für Identität, Beschriftung, Typ, Besitzer,
Containment, Verbindungsdimensionen, lokale Vollständigkeit und fehlende
Eingänge sind unabhängig vom Darstellungstext.

Lokales `recognized` zählt vorläufige Identitäten, `recognizedAtTarget` deren
Vorkommen am jeweiligen Parent/Endpunkt. Das bestätigt keine unabhängige
Beziehungsprüfung. `local.containmentRelations` und `childRoles` zählen diese
Prüfung gesondert. `unresolvedSubmission` zählt offene Identitäten,
`unresolvedChecks` Verbindungen mit noch ungeklärten Einzelprüfungen;
`deviating` zählt nachgewiesene individuelle Abweichungen.
Die bisherigen unabhängigen Containmentbelege bleiben bei Abhängigkeiten
ungeklärt. Revision 1.2 kann daneben einen erfüllten oder verletzten Fakt
unter vorläufiger Zuordnung ausweisen; dessen `basis` bleibt ausdrücklich
`conditional_mapping`. Bei anderen Endpunkten ist
die Orientierung ungeklärt, sofern nicht bereits die Gerichtetheit abweicht.
Ohne individuelle Verbindungszuordnung werden keine Gegenstücke aus einer
Gruppe gewählt; Parallelverbindungen bleiben entsprechend offen.

Unbekannte IDs oder Objektarten verletzen den Vertrag und werden kontrolliert
abgelehnt. Für unterstützte, unsichtbare Container verwendet die Anzeige den
nächsten sichtbaren Parent; die Annotation behält ihre Original-ID. Fehlt ein
darstellbares Ziel, bleiben die Befunde in der Sidebar verfügbar. Gruppenicons
adressieren die Endpunkte der Gruppe. Das Frontend liest Status und Codes und
führt keinen Graphvergleich aus. Der nachgelagerte Feedbackbericht bewahrt
seine bisherigen Matcher-Kategorien und ergänzt `analyticalSummary`.

## Lokale Regression

```powershell
python -m unittest discover -s dagu/workflow-services/analytical-feedback/tests -q
```

27 gezielte Tests prüfen Kategorien, unabhängige/abhängige Containmentbelege,
verschobene Attribute, fehlende Kinder, offene Gegenstücke, Rollenwechsel,
Source/Target/Richtung/Typ, Parallelverbindungen, ungerichtete Schleifen,
Original-IDs, Codes, Determinismus sowie stdout und den Feedbackverbraucher.
Schema und echter Frontendadapter werden mit dem bereits installierten
TypeScript/AJV aus `web/node_modules` geprüft; ohne diese Werkzeuge wird nur
dieser Test explizit übersprungen. Die verwendeten Schemaschlüssel gehören zur
gemeinsamen Teilmenge von Draft 7 und 2020-12.

Zusätzlich werden die gespeicherten Modell-Snapshots Baseline, M03, M05 und
M06b mit dem bestehenden Parser und der vorhandenen Repository-Sprachdefinition
auf unveränderte IDs und Beobachtungen geprüft. Eine weitere Prüfung verwendet
die tatsächliche Korrespondenzbildung mit vollständigen generischen
Kompatibilitätskandidaten und projiziert ihre Matcher-Fakten. Dabei werden keine
Embeddings oder Synonymscores neu berechnet. Das rekonstruiert keine historische
eingefrorene Sprach-/Hash-/Kandidatenkette. Ohne gelieferte Matcher-Fakten bleibt
der bisherige Beobachtungspfad unverändert konservativ. Insgesamt 138 betroffene
Matcher-Regressionen sind einschließlich Fakten-, Identitäts-, Positions- und
Verbindungsfällen geprüft. Vollständige Pipeline
und Kubernetes-Jobs werden für diese Prüfungen nicht gestartet.

## Umsetzungsschritte der Evidenzrevision

| Schritt | Geänderte Dateien (Servicepfade gekürzt) | Lokales Ergebnis |
| --- | --- | --- |
| 1. Identitätsevidenz | Matcher: `identity_evidence.py`, `assignment_capacity.py` | Exakter Anker, Typ allein und Zyklus geprüft; bestanden |
| 2. Identität / Position | Matcher: `correspondence_state.py`, `facts.py`, `main.py` | Falscher und ungeklärter Parent; Identität bleibt erhalten; bestanden |
| 3. Gemeinsame Kinder | Matcher: `structural_evidence.py`, `matching.py`, `identity_evidence.py` | Unterscheidende Kombination, 2/3-Teilmenge, symmetrische Parents, globale Konkurrenz; bestanden |
| 4. Einzelbefunde | Matcher: `facts.py` | Kinderlisten, Rollen, Platzierung, Abwesenheit und Anzeigeziele; bestanden |
| 5. Verbindungen | Matcher: `initial_recognition.py`, `initial_evaluation.py` | Eindeutige Endpunkte mit falschem Typ / Richtung, veränderte Endpunkte mit Textanker, mehrdeutige Parallelverbindungen; bestanden |
| 6. Feedbackcheckliste | Analyse: `fact_projection.py`, `analysis.py`, `analysis_contract.py`, Schema; Frontend: `analysisFeedback.ts`, `analysisFeedbackGraph.ts`, `AnalyticalFeedbackPanel.vue` | Exakte Projektion, Identitätsstatus, 2/3 plus verschobenes Child, deduplizierte Ziele, Schema, echter Adapter, Lint und Typprüfung; bestanden |
| 7. Sprachunabhängigkeit | Matcher-Regeln und generische Evidenzfixtures | Ausgetauschte Typ-, Sprach- und Rollennamen; unvollständige Graphen ohne Vollständigkeitsbehauptung; bestanden |
| 8. Regression | Matcher-/Analysetests, gespeicherte Modellfixtures | 138 Matcher- und 27 Analyse-/Vertragsprüfungen; alle 165 bestanden |
| 9. Bereitstellung | Serviceversionen, Compose, Workflow und READMEs | MCP-Preview gültig; Matcher `v3`, Analyse / Feedback `v6` gebaut, importiert und Digests abgeglichen; keine Jobs gestartet |
