# 06 · Admin-Auswertungsansicht (Modeling Editor › Sidebar › Auswertungen)

> **Zielkonzept** · Stand 16.11.2026 · Komponenten `EvaluationSidebar.vue`, `AnalyticalFeedbackPanel.vue`, `AnalysisObjectDetail.vue`, `SimilarityEvidence.vue`, Hilfen `utils/analysisFeedback.ts`, `utils/analysisFeedbackGraph.ts`
> **Teil A** beschreibt die Zielstruktur, die ausschließlich bereits veröffentlichte Workflow-Artefakte darstellt (umgesetzt).
> **Teil B** sammelt Erweiterungen, die neue Daten oder Verfahren erfordern (**nicht umgesetzt**).

---

## Teil A · Zielstruktur (umgesetzt)

### A1. Nutzer, Aufgabe, Abschluss

| | |
|---|---|
| **Rolle** | Administration/Moderation (Service-Perspektive). Studierende sehen weiterhin nur die Erkennungsübersicht. |
| **Ziel** | Nachvollziehen, *was* der Matcher je Objekt festgestellt hat und *warum* – um Musterlösung, Schwellen und Verfahren zu beurteilen. |
| **Ablauf** | Auswertung öffnen → Überblick lesen → auffällige Befunde in einer geordneten Liste abarbeiten (oder Element im Diagramm anklicken) → je Objekt die Begründung prüfen → nächstes Objekt. |
| **Abschluss** | Für jedes interessierende Objekt ist klar: Gegenstück, Identitätsstatus mit Begründung, Abweichungen, offene Punkte samt Grund. |

### A2. Grundsätze

1. **Drei Begriffe strikt trennen** – jede Anzeige gehört zu genau einem davon:
   - **Zuordnung** – Vorschlag des Matchers (`mapping`, `mappingReason`). Vorläufig, bis die Identität belegt ist.
   - **Identität** – Ergebnis der Identitätsprüfung (`identity.status`, Kriterien). Nur *eindeutig erkannt* zählt in der Erkennungsquote.
   - **Prüfungen** – Eigenschafts-/Strukturfakten (`facts[]`) unter der Zuordnung: erfüllt, abweichend, offen, nicht anwendbar.
2. **Keine neue Bewertung im Frontend.** Jede Aussage leitet sich aus einem vorhandenen Artefakt ab (Matcher-Fakt, Kandidatenmatrix, Graph-Diagnose). Begründungstexte formulieren nur die im Matcher implementierte Regel aus (GM-15, GM-26, Abschnitt *Ebene G* in `04-GRAPH-MATCHING.md`).
3. **Konkret statt pauschal.** Keine allgemeinen Vorbehalte („Alle Zuordnungen sind vorläufig“). Stattdessen pro Objekt: *wodurch* belegt, *was* fehlt, *wovon* es abhängt.
4. **Agenda statt Fließtext.** Pro Objekt eine feste Reihenfolge: Ergebnis → Zuordnung & Identität → Textähnlichkeit → Prüfungen → Struktur → technische Angaben.
5. **Ein Marker je Diagrammobjekt.** Keine überlagerten Icons; der Marker zeigt den schwersten Status, der Tooltip alle Befunde.

### A3. Gesamtaufbau der Service-Ansicht

```text
Toolbar (Zurück · Laufname · Aktualisieren)
Perspektive [Service | Studierende]
Laufkopf: Status · Zeit · Musterlösung (einmalig) · Fortschritt nur solange der Lauf aktiv ist
Tabs: [Überblick] [Befunde (n)] [Technik]
 ├─ Überblick
 │   • Erkennung je Vergleichsgruppe (Quote, keine Note)
 │   • Befundzählung als Einstieg: Abweichungen · Ungeklärt · Gestützt · Erkannt · Referenz offen → springt gefiltert in „Befunde“
 │   • Konfiguration: aktive Textähnlichkeitsverfahren und Schwellen
 │   • Datenqualität: Graphinterpretation Abgabe/Musterlösung + Parser-Diagnosen
 ├─ Befunde
 │   • Hinweis, falls das Diagramm vom ausgewerteten Stand abweicht
 │   • Filter (Status) + Suche (Beschriftung/ID)
 │   • Liste, nach Schwere sortiert: Icon · Beschriftung · Art · Kurzbegründung
 │   • Objektdetail (Agenda, s. A5) mit Zurück und Vor/Zurück-Navigation
 └─ Technik
     • Schrittverlauf, Roh-JSON, ZIP-Export (unverändert)
```

Klick auf ein Element im Diagramm öffnet „Befunde“ mit diesem Objekt; Auswahl in der Liste fokussiert das Element im Diagramm.

### A4. Statusvokabular (Liste, Marker, Detail)

| Anzeige | Bedingung (aus Artefakt) | Bedeutung für Admins |
|---|---|---|
| **Abweichung** | Mind. ein individueller Fakt `violated` (Gruppenfakten ausgenommen) | Gegenstück vorhanden, aber Eigenschaft/Struktur weicht nachweislich ab |
| **Ungeklärt** | `identity.status = unresolved` | Kein eindeutig belegtes Gegenstück; Grund steht im Detail (keine Evidenz *oder* Konkurrenz mit ebenfalls positiver Evidenz) |
| **Gestützt, nicht eindeutig** | `identity.status = supported` | Positive Evidenz, die Konkurrenten nicht ausschließt; zählt nicht als erkannt |
| **Eindeutig erkannt** | `identity.status = uniquely_supported` | Mind. ein Identitätsanker; Wiedererkennung ≠ Korrektheit |
| **Referenz offen** | `referenceHints[]` mit `reference.unresolved` | Referenzobjekt ohne identifiziertes Gegenstück – **nicht** als fehlend bewiesen |
| **Referenz fehlt** | `referenceHints[]` mit `reference.missing` | Abwesenheit durch Matcherfakt belegt |
| **Vorläufige Zuordnung** | Ältere Formate ohne Identitätsprüfung | Nur historische Läufe |

### A5. Objektdetail – feste Agenda

1. **Kopf:** Beschriftung, Art und konkreter Typ, Status-Chip.
2. **Ergebnis (Checkliste):** eine Zeile je Aussage mit Icon, z. B. „✓ Gegenstück *Kunde* (Klasse)“, „✓ Eindeutig über exakte Beschriftung“, „✗ Besitzer weicht ab“, „? 3 Prüfungen offen“.
3. **Zuordnung & Identität:**
   - Gegenstück in der Musterlösung und Zuordnungsregel im Klartext.
   - Begründungssatz des Identitätsstatus:
     - *eindeutig*: welche Kriterien als Anker entscheiden;
     - *gestützt*: welche positive Evidenz vorliegt und dass sie Konkurrenten nicht ausschließt;
     - *ungeklärt mit positiver Evidenz*: ein konkurrierendes Paar (gleiches Referenz- oder Abgabeobjekt) besitzt ebenfalls positive Evidenz – das ist der Fall „ungeklärt, obwohl positive Evidenz vorliegt“;
     - *ungeklärt ohne Evidenz*: keine tragfähige Evidenz.
   - Kriterien gruppiert nach Rolle: **Entscheidend** (Identitätsanker) · **Spricht dafür** · **Offen / nicht erfüllt** · **Nur Zulässigkeit** (Typkompatibilität, nie Beleg). Offene Kriterien nennen die Abhängigkeit („stützt sich auf *A ↔ B*, selbst nicht eindeutig“).
   - Konkurrierende Kandidaten mit gleicher normalisierter Beschriftung (NFC + Leerraum, wie GM-04).
4. **Textähnlichkeit** (nur Fachelemente, Daten aus `semantic-candidates/v1` + `semanticConfiguration`):
   - je berechnetem Verfahren eine Fortschrittsleiste über den Wertebereich der Methode mit **Strichmarke an der Schwelle**, Wert und Vergleich („0,83 ≥ 0,80“);
   - ohne konfigurierte Schwelle: Leiste ohne Marke und Hinweis, dass der Wert die Zuordnung nicht beeinflusst;
   - Konkurrenz: die stärksten alternativen Kandidaten (andere Referenz- bzw. Abgabeobjekte) mit Werten; markiert, welche über der Schwelle liegen. Textähnlichkeit ankert nur, wenn genau ein offenes Paar über der Schwelle liegt (GM-26);
   - Text nicht bewertbar: Grund (`missing_text`, `unsupported_text`).
5. **Prüfungen:** gruppiert **Abweichend → Offen → Erfüllt** (*nicht anwendbar* nur als Anzahl). Jede Zeile: Prüfung, Ergebnis, Beweisbasis, Klartextgrund, Zähler. Offene Vollständigkeitsprüfungen mit übereinstimmenden Zählern nennen die Ursache: die Graphinterpretation ist nur teilweise vollständig (Parser-Diagnosen), daher keine bestätigte Vollständigkeit.
6. **Struktur** (sofern vorhanden): Besitzer/Parents, Kinderbefunde, Verbindungsendpunkte, Containment-Beziehungen, Verbindungsgruppen (stets als Gruppenaussage gekennzeichnet).
7. **Technische Angaben** (aufklappbar): Original-IDs, Abhängigkeiten, Hinweis-Codes und Parameter, betroffene Parser-Diagnosen.

### A6. Datenquellen

| Anzeige | Quelle (Schritt der Auswertung) |
|---|---|
| Objekte, Beschriftung, Typ, Graphvollständigkeit, Parser-Diagnosen | `parse_model_<key>` · `graph-result/v1` |
| Kandidaten, Scores, Methoden, Wertebereiche, Textstatus | `match_synonyms_<referenceKey>` · `semantic-candidates/v1` |
| Schwellen (`minimumSimilarity`), Konfigurationsstatus, Kandidatenhash-Bindung | `match_graph_<referenceKey>` · `reference-comparison/v2` |
| Annotationen, Identität, Fakten, Hinweise, Gruppen, Erkennung | `generate_analytical_feedback_<referenceKey>` · `analysis-feedback/v3` |

Kandidatenmatrix und Vergleich werden nur zusammen angezeigt, wenn `candidateHash` und `evaluationId` übereinstimmen; sonst entfällt der Abschnitt Textähnlichkeit mit Hinweis.

### A7. Diagramm-Markierungen

- Pro Diagrammobjekt genau **ein** Marker oben rechts: schwerster Status aus eigener Annotation, Positionsbefunden anderer Objekte, Referenzhinweisen und Verbindungsgruppen.
- Tooltip listet alle Befunde zeilenweise; Klick wählt das Objekt und öffnet das Detail.
- Markierungen nur, wenn das Diagramm dem ausgewerteten Stand entspricht (bestehende Snapshot-Prüfung).

---

## Teil B · Erweiterungsvorschläge (nicht umgesetzt)

Jeder Punkt benötigt Änderungen außerhalb der reinen Darstellung. Reihenfolge = empfohlene Priorität.

| # | Vorschlag | Nutzen | Erforderliche Änderung |
|---|---|---|---|
| B1 | **Score und Schwelle direkt im Identitätskriterium `text_similarity`** | Detail muss die Werte nicht aus der Kandidatenmatrix rekonstruieren; exakt die vom Matcher verwendeten Werte | `analytical-feedback/src/analysis_contract.py` · `compact_identity()` um `scores`, `minimumSimilarity` ergänzen (Matcher liefert sie bereits); Vertragsversion `analysis-feedback/v3` erweitern; Frontend-Validierung in `adaptCurrentAnalysis()`; Service-Version/Image-Tag erhöhen |
| B2 | **Blockierende Konkurrenzpaare je Identität** („ungeklärt wegen *X ↔ Y*“ auch für Kinder-/Besitzer-Evidenz) | Vollständige Antwort auf „warum nicht eindeutig?“; heute nur für gleiche Beschriftung und Textähnlichkeit ableitbar | `identity_evidence.py` · `evaluate_identity()` gibt je Paar `competitors[]` aus (die `strong`-Menge existiert bereits); `facts.py` übernimmt sie in `identity.*`; `compact_identity()` + Frontend |
| B3 | **Grund zurückgestellter semantischer Vorschläge** (Dominanz, Ownerkonflikt, Kapazität; GM-16–18) | Admins sehen, warum ein Paar über der Schwelle nicht zugeordnet wurde | Heute nur in `diagnostics.semanticRefinement` bei `GRAPH_MATCHING_DIAGNOSTICS=1`; kompaktes Feld `deferredReason` je Kandidat in `reference-comparison/v2` und Weitergabe an Annotationen |
| B4 | **Verbindungstext-Ähnlichkeit anzeigen und nutzen** | Linien mit ähnlicher, nicht exakt gleicher Beschriftung erklärbar | Matcher nutzt `connectionTextMatrix` derzeit nicht (Grenze 2 in `04-GRAPH-MATCHING.md`); erst Verfahren spezifizieren (GM-19 erweitern), dann Darstellung analog A5.4 |
| B5 | **Kalibrierungskontext an der Schwelle** (Precision/Recall der gewählten Schwelle) | Schwelle fachlich einordnen („0,80 ≈ Precision 0,86 / Recall 0,31“) | Kalibrierungsskript veröffentlicht ein versioniertes Artefakt; Auswertungsparameter verweisen auf die Kalibrierungsversion; API liefert es mit |
| B6 | **Vergleich über mehrere Musterlösungen** (welche passt am besten, Objekt je Musterlösung) | Kein manuelles Umschalten | Aggregationsregel fachlich festlegen (keine Note, AF-20); `feedback-generation` oder API liefert Paarübersicht; UI-Spalte je Musterlösung |
| B7 | **Manuelle Bestätigung/Korrektur einer Zuordnung durch Admins** | Goldkorpus aus realen Abgaben aufbauen, Fehlzuordnungen markieren | Neues Datenmodell (Annotation je Auswertung/Objekt), API-Endpunkte mit Rechten, keine Rückwirkung auf Matcher-Ergebnisse ohne neuen Lauf |
| B8 | **Deep Link auf Objekt** (`?evaluation=…&object=…`) | Befunde teilen, Reproduktion | Router-Query in `ViewModeling.vue` auswerten und an die Sidebar durchreichen |
| B9 | **Abhängigkeitsgraph der Identitäten** (welche Anker tragen welche Kinder/Linien) | Kettenwirkungen erkennen | Alle Daten (`dependsOn`) vorhanden; eigene Visualisierung nötig – bewusst zurückgestellt, um die Sidebar nicht zu überladen |

**Regel für neue Punkte:** Erst die fachliche Aussage und ihren Matcher-Fakt festlegen (siehe Änderungsregel in `05-ANALYTICAL-FEEDBACK.md`), dann Darstellung ergänzen. Neue Anzeigeaussagen ohne Quelle werden nicht im Frontend berechnet.
