# 04 · One-to-One Graph Matching

> **Ist-Dokumentation** · Stand: `dagu(6).zip`, 16.11.2026 · Service `one-to-one-graph-matching` · `reference-comparison/v2`  
> **Aufgabe:** Für Abgabe und **eine** Musterlösung aus zulässigen Kandidaten und Graphstruktur eine **partielle 1:1-Korrespondenz** entwickeln, ihre Identitätsevidenz bewerten und **Eigenschaften/Relationen getrennt** prüfen. **Noch keine Note und keine endgültige Korrektheitsaussage über das Gesamtmodell.**

## Gesamtbild: genau ein Graph-Matching-Aufruf

```text
Snapshot + zwei Graphen + zwei Inventare + semantic-candidates/v1
  │
  ├─ A. Herkunft & vollständige Kandidaten prüfen / Graphindizes bilden
  ├─ B. Exakte und strukturelle Elementvorschläge erzeugen
  ├─ C. Konfigurierte semantische Vorschläge ergänzen
  ├─ D. Verbindungen vorläufig zuordnen
  ├─ E. Konkrete Strukturbeziehungen bewerten
  ├─ F. Identitätsevidenz ausgewählter Paare bewerten
  ├─ G. Eigenschafts-, Struktur- und Anwesenheitsfakten erzeugen
  └─ H. Kompaktes reference-comparison/v2 veröffentlichen
```

**Wichtig zum Ist-Zustand:** B, C und D besitzen **noch eigene Vorschlags-/Konkurrenzphasen**. E–G erläutern Ergebnisse und stellen zusätzliche Fakten fest; E/F sind **keine zweite vollständige Graphüberlagerung**. Eine vollständig zentrale Identitätsauswahl ist **noch nicht** umgesetzt.

## Eingaben und grundlegende Verbote

| Quelle | Verwendet für |
|---|---|
| `graphs/submission.json`, `graphs/<referenceKey>.json` | Knoten, konkrete Typen, Sprachversion, `contains`-Hierarchie, Verbindungsendpunkte, Richtung |
| `labels/submission.json`, `labels/<referenceKey>.json` | Verlässliche Text-/Labelstatus für Eigenschaftsfakten |
| `candidates/<referenceKey>.json` | **Vollständiger zulässiger Kandidatenraum** plus methodenspezifische Textscores |
| `comparisonConfig.graphMatching.minimumSimilarity` | Optional aktivierte Methoden-Schwellen; Standard `{}` = keine semantischen Vorschläge und keine Textähnlichkeitsanker. Der Workflowparameter `levenshtein_threshold` setzt sie über `workflow-data` als `{levenshtein: x}` (zusammen mit `semantics.methods: [levenshtein]`) |

**GM-01 · Integrität:** Vollständige `workflow-result/v1`-Hüllen, Snapshot-/Quellen-/Sprach-/Graph-/Inventar-/Kandidatenhashes werden geprüft. Die Kandidatenmatrix muss **alle und nur** die kompatiblen Fachobjektpaare abbilden; keine stillschweigend fehlenden Konkurrenzpaare. Fehler → kein Erfolgsergebnis.

**GM-02 · Paarzulässigkeit:** Beide Graphobjekte benötigen gleiche Sprach-ID und **Sprachversion**. Wenn **beide** eine explizite Vergleichsgruppe besitzen, muss diese gleich sein; bei **beidseitig fehlender** Gruppe muss der konkrete Typ gleich sein. Gemischte Gruppierung ist unzulässig. `type_compatibility` ist **kein Identitätsbeweis**.

**GM-03 · Modellobjekte:** Freie Fachkandidaten sind `modelElement` mit semantischer Vergleichsrolle. Strukturelle Container sind keine frei wählbaren semantischen Instanzen; Verbindungen werden gesondert zugeordnet.

## Ebene B · Erstzuordnung von Fachobjekten

| Reihenfolge | Evidenzverfahren | Aktuelle Entscheidungsregel |
|---|---|---|
| **GM-04 · Exakter Textanker** | Nichtleere, NFC-/Whitespace-normalisiert identische Texte aus **zulässigen Paaren** | `necessary_pairs()` bestimmt Paare, die in **jeder maximalen 1:1-Zuordnung des Exakttext-Kandidatengraphen** vorkommen. Nur diese werden als `unique_exact_label` vorgeschlagen. Mehrdeutige Kombinationen bleiben offen. **GM-04a:** Ein exakter Anker wird zum Prüffall (`label_structure`, als Konflikt reserviert, kein automatischer Tausch), wenn seine Substruktur-Kinder vollständig und geschlossen ein *anderes* Referenzobjekt abbilden **und** seine über Verbindungen zugeordneten Nachbarn diesem anderen Objekt mehr entsprechen. Beispiel: vertauschte Beschriftungen Etage/Laborraum (v15 S06). Gegenbeispiel: getauschte Attributlisten bei richtigen Namen (v14 M05) bleiben Anker, weil die Nachbarn die Namen stützen. |
| **GM-05 · Zugehörigkeit zum erkannten Besitzer** | Exakte, zunächst mehrdeutige Kinder | Ein bereits unabhängig exakt verankerter Besitzer kann ein Kindpaar über konsistente `contains`-/Owner-Evidenz stützen. Nur beidseitig eindeutige Vorschläge (`consistent_owner_anchor`), mit Besitzerabhängigkeit. |
| **GM-06 · Residualer Exaktanker** | Nach vorläufigen Reservierungen eindeutig gewordene Textpaare | `unique_exact_after_reservations` nur mit expliziter Abhängigkeit von den reservierten Paaren, die Alternativen ausgeschlossen haben; eine rein zufällig verbliebene Paarmöglichkeit genügt nicht. |
| **GM-07 · Unabhängige Kinder → Parent** | Bereits vorgeschlagene, **nicht vom zu beweisenden Parent abhängige** Kinder | Bei eindeutig unterstützter Parentkombination `independent_child_evidence`. Konfliktkinder, Konkurrenten und fehlende unabhängige Stützung führen zu Zurückstellung. **GM-07a:** Blockierend ist ein Konfliktkind, dessen Identität aus seinem Label allein folgt (`unique_exact_label`), z. B. `Geräteraum/Größe` (v15 S04); ein nur durch Ausschluss zugeordnetes Kind (`unique_exact_after_reservations`) blockiert nicht, z. B. verschobene `ProjektNr.` bei `Forschungsvorhaben` (v14 M08). |
| **GM-08 · Gemeinsame Kinderstruktur** | Mehrere einzeln mehrdeutige Kinder; verglichen werden u.a. Text, Vergleichsschlüssel und Strukturpfade/Rollen | Lokale maximale Paarbarkeit wird geprüft. Ein Parent-Anker `combined_child_structure` erfordert eine **geschlossene** vollständige Kinderkomposition, eindeutige Unterscheidbarkeit, bekannte Pfade/Rollen und ausreichende Interpretationsvollständigkeit. Teiltreffer bleiben positive Evidenz, aber kein automatischer Anker. |
| **GM-09 · Kinder nach erschlossenem Parent** | Neuer strukturell gestützter Parent | Zuvor mehrdeutige exakte Kinder können anschließend als `consistent_owner_anchor` ergänzt werden – mit Abhängigkeit vom erschlossenen Parent. |

### Abhängigkeiten und Kapazität

- **GM-10 · 1:1-Regel:** Kein ausgewähltes Referenzobjekt darf zwei Abgabeobjekte belegen und umgekehrt. Konflikte und nicht verfügbare Abhängigkeitsanker blockieren den Vorschlag; sie erzeugen **keinen erzwungenen Sieger**.
- **GM-11 · Kapazität:** Bipartite maximale Zuordnungsgröße ist eine **Machbarkeitsbedingung**, kein Identitätsbeweis. Vorschläge sollen die maximal mögliche Belegungszahl der zulässigen Kandidaten nicht reduzieren. Die aktuelle `capacity_preserving_proposals()` prüft einzeln und dann **gemeinsam pro Kandidatenkomponente**.
- **GM-12 · Grenze der derzeitigen Logik:** Sind mehrere einzeln zulässige Vorschläge **innerhalb derselben Komponente zusammen** unzulässig, verwirft die aktuelle Funktion mitunter auch konfliktunabhängige Vorschläge. Das ist ein **bekannter, nicht als behoben dokumentierter Restfall**. Keine Statusaufwertung oder neue Prioritätsregel daraus ableiten.
- **GM-13a · Substruktur statt Platzierung:** Identitätsprägend ist ein Besitzer nur, wenn der `contains`-Pfad zu ihm über eine deklarierte Substruktur führt (mindestens eine `component`-Kante, z. B. SERM-Attributliste). Ein Fachobjekt, das nur per `content` in einem anderen liegt (Aufgabe in Lane, Element in Paket, heute auch UML-Klassenmitglieder), hat keinen Identitätsbesitzer: Besitzeranker, unabhängige Kinder, Kinderkombination, Besitzerkonflikt in der semantischen Verfeinerung und das Kriterium `identified_owner` ignorieren diese Platzierung. Lagefakten (`owner.*`, `containment.*`) bewerten sie weiterhin (`GraphIndex.owner()` vs. `identity_owner()`).
- **GM-13 · Kein Zirkelschluss:** Eine Kindzuordnung, deren Identität erst auf einer Parentannahme beruht, darf diese Parentidentität **nicht** als unabhängiger Beweis bestätigen. Abhängigkeiten werden beim Aufbau und später in der Identitätsbewertung berücksichtigt.

## Ebene C · Semantische Verfeinerung (optional)

```text
Aktivierte minimumSimilarity-Schwellen?
  nein → keine semantischen Identitätsvorschläge
  ja  → Scores je zulässigem Paar aus Kandidatenmatrix lesen
        → Methode(n) oberhalb ihrer jeweiligen Schwelle?
        → Konkurrenz und bereits reservierte IDs prüfen
        → Owner-Relation und Score-Dominanz prüfen
        → 1:1-Kapazität prüfen
        → ggf. provisional semantic proposal
```

| Regel | Ist-Verhalten |
|---|---|
| **GM-14 · Schwellen** | `comparisonConfig.graphMatching.minimumSimilarity` nennt **Methoden einzeln**. Werte müssen zum Scorebereich passen; `{}` bedeutet `not_configured`. Keine automatisch erfundene universelle Schwelle. Alternativ (exklusiv) `graphMatching.textEvidence.tiers`: geordnete Stufen mit eigener `minimumSimilarity`; ein Paar gehört zur ersten erfüllten Stufe, stärkere Stufen gewinnen die Konkurrenz und reservieren in der Identitätsbewertung zuerst (Konzept 07). |
| **GM-15 · Evidenz pro Paar** | `supported`, wenn mindestens eine aktivierte Methode ihren Grenzwert erreicht; sonst je Datenlage `below_threshold` oder `unavailable`. Mehrere Methoden werden nicht als Wahrscheinlichkeiten addiert. |
| **GM-16 · Konkurrenz** | Vorschlag nur, wenn seine Scores (über konfigurierte Methoden) und Owner-Rang **alle konkurrierenden zulässigen Kandidaten** dominieren; bei Gleichstand/unklaren Methoden zurückstellen. |
| **GM-17 · Strukturbedingung** | Bekannter Ownerkonflikt verhindert den **semantischen Vorschlag**; bei enthaltenen Objekten mit ungeklärter Besitzerlage wird er ebenfalls zurückgestellt. Wurzelobjekte ohne Besitzer können ohne Owneranker vorgeschlagen werden. |
| **GM-18 · Kapazität** | Semantische Vorschläge durchlaufen dieselbe kapazitätserhaltende Vorschlagsprüfung. |
| **GM-18a · Kinder semantischer Besitzer** | Zweiter Durchlauf: Substruktur-Kinder eines semantisch vorgeschlagenen Besitzerpaars konkurrieren nur innerhalb dieses Paars (Kandidaten mit anderem Besitzer zählen nicht), mit denselben Stufen und Schwellen und `dependsOn` auf das Besitzerpaar. In der Identität trägt `identified_owner`, wenn der Text innerhalb des eindeutig erkannten Besitzers notwendig ist. Beispiel: `Labor-Raum/RaumNr` ↔ `Laborraum/RaumNr.`. Ein falsch erkannter Besitzer zieht seine Kinder mit (sie fallen mit ihm). |
| **GM-18b · Graubereich mit Nachbarbestätigung** | Zuordnungsgrund `neighbor_confirmed_semantic_evidence`.  Nur Hauptelemente ohne Substruktur-Besitzer. Liegt ein Score unter der Stufenschwelle, aber über deren `confirmationFloor`, wird das Paar nur vorgeschlagen, wenn bereits zugeordnete Nachbarn es bestätigen und kein Konkurrent mindestens gleich viele Bestätigungen hat; `dependsOn` nennt die bestätigenden Nachbarpaare. Text-Identität bleibt `violated`, das Paar daher höchstens `supported`. Beispiel: `Lab Room` (0,76) über `Ausstattung Labor`; Gegenbeispiel `Scientist` ~ `Laborraum` (0,80) ohne passende Nachbarn. |

**Adapter:** `text_similarity.py` liest die Kandidatenmatrix und klassifiziert jedes zulässige Paar als `supported`, `below_threshold` oder `unavailable`. `semantic_refinement.py` (Vorschläge) und `identity_evidence.py` (Anker) nutzen denselben Adapter.

**Identität:** Ein semantischer Vorschlag ist erst dann eindeutig erkannt, wenn das Kriterium `text_similarity` unter allen offenen Paaren über der Schwelle **notwendig** ist (GM-26). Ein Vorschlag, der nur seine Konkurrenten dominiert, aber nicht eindeutig über der Schwelle steht, bleibt `supported`/`unresolved` und zählt **nicht**. Eine einzelne Schwelle ist eine harte Kante: Konkurrenten knapp darunter werden nicht berücksichtigt.

## Ebene D · Verbindungsvorschläge (nach Elementmapping)

| Regel | Ist-Verhalten |
|---|---|
| **GM-19 · Exakter Verbindungstext** | Nichtleerer, exakt gleicher Text (`connection` selbst oder passender `self`-Text aus `connectionTextMatrix`) kann `unique_exact_connection_label` begründen, sofern sprachlich kompatibel. |
| **GM-20 · Strenge Struktur** | `compatible_type_and_mapped_endpoints`: kompatibler Vergleichsschlüssel, auf Abgabeobjekte abgebildete Endpunkte, bekannte Richtung. Gerichtete Anschlüsse bewahren `source`/`target`; ungerichtete werden als Endpunktmenge betrachtet. |
| **GM-21 · Breitere Endpunktstruktur** | `unique_mapped_endpoints`: bei passender Sprache und identischer **ungerichteter Endpunktgruppe** kann eine Verbindung auch trotz Typ-/Richtungsabweichung als Kandidat in Betracht kommen. Konkurrenz muss eindeutig auflösbar sein. |
| **GM-22 · Parallele Linien** | Notwendige Paare der jeweiligen Kandidatengraphen werden vorgeschlagen; mehrere nicht unterscheidbare parallele Verbindungen bleiben individuell ungeklärt. |

**Verbindungsidentität ≠ Eigenschaften:** Eine erkannte Linie mit abweichendem konkretem Typ, Endpunkt oder Richtung kann einzeln einen Fehlerfakt erhalten; gruppenweite Unterschiede begründen keine automatische individuelle Fehlidentität.

## Ebene E/F · Struktur und Identität **getrennt** bewerten

### E. Strukturrelationen

- **GM-23 · Containment:** Jede Referenz-`contains`-Relation wird mit den bisher vorgeschlagenen Korrespondenzen, unmittelbaren Parents, Rollen und möglichen Zwischencontainern verglichen. Die unabhängige Beweisanforderung ist strenger als einfache Ownerkonsistenz. `satisfied`, `violated`, `unresolved` sind möglich; nicht unabhängige/zirkuläre Beweise bleiben offen.
- **GM-24 · Strukturelle Container:** Dürfen nur aus eindeutig passenden, von bereits verankertem Parent abhängigen verschachtelten Definitionen abgeleitet werden; keine freie strukturelle 1:1-Kandidatenwahl.
- **GM-25 · Verbindungsgruppen:** `provisionalConnectionStructure` vergleicht Endpunktgruppen unabhängig von der individuellen Identität paralleler Linien. Richtung, Typ, Konfiguration dürfen abweichen; ein Gruppenbefund ist kein einzelner Verbindungsfehler.

### F. Identitätsbewertung

| Methode / Evidenz | Als Identitätsanker verwendbar? |
|---|---|
| `type_compatibility` | **Nein** – nur Vergleichszulässigkeit |
| `exact_label` | **Ja, wenn** innerhalb aller evidenzgestützten Alternativen notwendig/eindeutig |
| `independent_children` | **Ja, wenn** Abhängigkeiten bereits unabhängig geklärt |
| `combined_children` | **Nur** bei vollständiger geschlossener Kombination und eindeutiger Konkurrenz |
| `identified_owner` | Bedingt; muss diskriminieren, unabhängig sein und zulässige Stützung besitzen |
| `connection_structure` | Ja, wenn individuell eindeutig und die benötigten Endpunktidentitäten abgesichert sind |
| `text_similarity` | **Ja, wenn** Score ≥ Schwelle und das Paar unter allen offenen Paaren über der Schwelle notwendig/eindeutig ist; wird für alle zulässigen Paare berechnet, damit Konkurrenz sichtbar bleibt. Ohne Schwelle nicht vorhanden. Ersetzt das frühere `semantic_proposal` (Identitätsevidenz `1.1`). |

**GM-26a · Verbindungen und Konflikte:** Bei zwei unbeschrifteten Verbindungen ist `exact_label` `not_applicable` (nicht `violated`). `connection_structure` wird `unresolved`, solange die Endpunkte selbst nicht eindeutig erkannt sind (wie `identified_owner`/`independent_children`). Ein nach GM-04a zurückgehaltener Anker erhält das Kriterium `label_structure: violated`, das über den Analysebericht im Frontend als „Beschriftung widerspricht Struktur“ erscheint.

**GM-26 · Status:** `uniquely_supported` = eindeutige, nicht zirkuläre Identitätsevidenz für das ausgewählte Paar; `supported` = positive, aber nicht hinreichende Evidenz; `unresolved` = kein hinreichend gestützter, eindeutiger Vorschlag. Ein `provisional`-Paar ist **nicht automatisch** `uniquely_supported`.

**GM-27 · Evidenzzeitpunkt:** `evaluate_identity()` bewertet die **bereits vorgeschlagenen** Paare und erklärt auch konkurrierende zulässige Paare; es ist **kein vollständig zentraler Korrespondenz-Selektor**. Die Statusbegründung setzt eine nachweisbare 1:1-Zuordnung voraus.

## Ebene G · Faktauswertung (keine neue Identitätswahl)

| Prüffamilie | Was wird verglichen? | Regel für Aussage |
|---|---|---|
| **GM-28 · `label.*`** | Text der zugeordneten Elemente/Verbindungen | `equal`/`different` nur bei verfügbarem Text; bei fehlendem/nicht unterstütztem Label `label.unavailable: not_evaluated` – nicht „nicht anwendbar“. |
| **GM-29 · `type.*`** | Konkreter Typ der zugeordneten Instanzen | `satisfied` bei gleichem Typ, `violated` bei bekanntem Unterschied innerhalb zulässiger Vergleichsklasse; nicht automatisch falsche Identität. |
| **GM-30 · `owner.*` / `containment.*`** | Fachlicher Besitzer, Parent-ID und direkte Relation/Rolle | Korrekte, verschobene oder ungeklärte Position **unter den nötigen Identitätsannahmen**. Bekannte Konflikte dürfen identifizierte Kinder nicht einfach „unsichtbar“ machen. |
| **GM-31 · `children.complete`** | Semantische Kinder über Strukturcontainer hinweg bis zum nächsten Fachobjekt | Erwartet/beobachtet/zugeordnet, verschobene/offene/fremde/zusätzliche Kinder, Rollen und Pfade. Lokale Vollständigkeit nur bei hinreichend vollständigen und eindeutigen Daten. |
| **GM-32 · `direct_children.complete`** | **Unmittelbare** Parent→Child-Beziehungen | Zusätzlich Containerpfad/Rollen berücksichtigen; nicht mit semantischen Gesamtkindern gleichsetzen. |
| **GM-33 · `connection.*`** | Individuell zugeordnete Linie: Typ, Endpunkte, `source`, `target`, Richtung | `satisfied`, `violated` oder `unresolved` je nach Daten-/Mappinglage; Endpunktgruppen separat halten. |
| **GM-34 · `connection_group.*`** | Gruppen von Linien zwischen gemappten Endpunkten | Aussage ausschließlich **auf Gruppenebene**, nicht jedem Einzelobjekt als individueller Fehler zurechnen. |
| **GM-35 · `incoming/outgoing/undirected/connections.complete`** | Lokale Anzahl und zugeordnete Verbindungen pro erkanntem Fachobjekt | Gesamt- und Richtungszahlen getrennt, offene Endpunkte/partielle Graphen als Einschränkung. |
| **GM-36 · `counterpart.*`** | Vorhandenes/unzugeordnetes Gegenstück; Anwesenheit | `unmatched` zunächst `unresolved`; `missing` nur bei aus vollständiger Graphbeobachtung/ausreichender 1:1-Beweislage belegter Abwesenheit. |
| **GM-37 · `identity.*`** | Identitätsstatus und tragende Kriterien | Als separater Fakt für Feedback und Erkennungsstatistik, **nicht** durch Eigentums-/Labelabweichung überschreiben. |

**Faktstatus:** `satisfied` · `violated` · `unresolved` · `not_evaluated` · `not_applicable`. Jeder Fakt enthält Beweisbasis (`direct_observation`, `independent_evidence`, `conditional_mapping`), betroffene Original-IDs und gegebenenfalls ein gemeinsames `findingId` für denselben Positionsfehler.

## Ebene H · Standardausgabe vs. Diagnostik

```text
reference-comparison/v2 (im Normalbetrieb)
  mapping.provisionalElements[] / provisionalConnections[]
  unresolvedReferenceIds[] / unresolvedStudentIds[]
  unresolvedReferenceConnectionIds[] / unresolvedStudentConnectionIds[]
  propertyFacts {version, items[]}
  semanticConfiguration {configurationStatus, minimumSimilarity}
  Provenienz, completeness, comparisonHash

nur bei GRAPH_MATCHING_DIAGNOSTICS=1 zusätzlich:
  diagnostics {candidatePairs, decisionEvents, identityEvidence,
               semanticRefinement, childOwnerEvidence,
               Containment-/Connection-Detailanalysen, Metriken, ...}
```

**GM-38 · Datensparsamkeit:** Die umfangreichen Zwischenauswertungen werden heute **weiterhin intern berechnet** und im Normalbetrieb vor der Serialisierung entfernt. Weniger JSON bedeutet deshalb **nicht automatisch weniger CPU-/RAM-Aufwand**.

**GM-39 · Kein Score:** Der Graphvergleich setzt `assessmentAvailable: false` und `status: partial`/provisorische Vollständigkeit. Die spätere Erkennungsquote zählt ausschließlich eindeutige Identitäten, nicht „korrekte Struktur“ und nicht alle `provisional`-Paare.

## Änderungslandkarte – genau hier ändert sich welche Regel

| Regeln | Verantwortlicher Code |
|---|---|
| GM-01–03: Artefakte, Kompatibilität, Graphindizes | `artifacts.py`, `graph_index.py` |
| GM-04–09: Text-/Strukturvorschläge | `matching.py`, `correspondence_state.py`, `structural_evidence.py` |
| GM-10–12: globale Paarbarkeit, Kapazität, Konkurrenz | `assignment_capacity.py`, `correspondence_state.py` |
| GM-14–18: semantische Vorschläge | `semantic_refinement.py` |
| GM-19–22, GM-25: Verbindungen | `initial_recognition.py` |
| GM-23–24: Containment-/Owner-Evidenz | `initial_structure.py`, `structural_evidence.py` |
| GM-26–27: Identitätsbewertung | `identity_evidence.py` |
| GM-28–37: Eigenschafts-, Struktur-, Präsenzfakten | `facts.py` |
| GM-38–39: Orchestrierung, Projektion, Herkunft | `main.py`, `initial_evaluation.py` |
| Workflow-Aufruf | `dagu/workflows/model-evaluation-graph-matching.yaml` · `one-to-one-graph-matching-pair` |
| Tests | `one-to-one-graph-matching/tests/` |

## Noch offene fachliche/architektonische Grenzen (nicht als implementiert ausgeben)

1. **Konkurrenzentscheidung:** Ein gemeinsam konflikthafter Vorschlagssatz kann in derselben Komponente noch konfliktunabhängige zulässige Vorschläge verlieren (GM-12).
2. **Semantische Identität:** Nur Levenshtein ist angebunden; die Schwelle ist noch nicht an einem Gold-Korpus kalibriert, Groß-/Kleinschreibung wird nicht normalisiert, Verbindungstexte nutzen keine Ähnlichkeit.
3. **Zentrale Entscheidung:** Text-/Owner-/Kinder-/Semantik-/Verbindungsphasen sind noch nicht durch eine vollständig gemeinsame, evidenzgetriebene Auswahl ersetzt (GM-27).
4. **Selektive Semantik:** Der vorgelagerte Synonymdienst liefert weiterhin die **vollständige** zulässige Kandidatenmatrix; keine produktive aggressive Textanker-Trimmung.
5. **Ressourcen:** Diagnosedaten werden vielfach noch berechnet, auch wenn sie nicht ausgegeben werden.

**Änderungsregel:** Zuerst das gewünschte `GM-xx`-Verhalten **mit positivem und adversarialem Gegenbeispiel** spezifizieren, dann den benannten Codepfad ändern. Eine verbesserte Erkennungsquote darf nicht durch falsche 1:1-Identitäten erkauft werden.
