# 05 · Analytical Feedback

> **Ist-Dokumentation** · Stand: `dagu(6).zip`, 16.11.2026 · Service `analytical-feedback` · `analysis-feedback/v3`  
> **Aufgabe:** Die vom Graph-Matcher **bereits festgestellten** Zuordnungen und Fakten für konkrete Diagrammobjekte und eine dynamische Erkennungsübersicht aufbereiten. **Keine neue Identitäts- oder Strukturentscheidung.**

## Ablauf auf einen Blick

```text
Snapshot + Graphen + Kandidaten + reference-comparison/v2
  → vollständige Hash-/Quellenkette validieren
  → ausgewählte Zuordnungen und Fakten indexieren
  → Annotation je Abgabeobjekt + Referenzhinweise erstellen
  → dynamische Erkennungsgruppen aus Musterlösung zählen
  → kompakte Analyse validieren, hashen, speichern und via stdout ausgeben
  → Dagu übergibt analysisPath an Feedback Generation
```

## Eingabe → Ausgabe

| Eingang | Verwendung |
|---|---|
| `comparisons/<referenceKey>.json` | Verbindliche Zuordnungen, Identitätsevidenzen und Eigenschafts-/Strukturfakten |
| Referenz-/Abgabegraph, Textinventare, Kandidaten, Snapshot | Herkunft, ID-Gültigkeit, Vergleichsgruppen und **Hash-Konsistenz** überprüfen; keine neue Korrespondenz bestimmen |

**Ausgabe:** `analysis/<referenceKey>/<analysisKey>.json` und `stdout` (`analysis-result.json`), `workflow-result/v1 → result.schema = analysis-feedback/v3`. Dagu prüft `analysisPath`/`analysisKey`, reicht den Pfad an `feedback-generation` weiter und speichert zusätzlich dessen `feedback-result.json`.

## 1. Objekthinweise: Was kann das Diagramm lesen?

| Struktur | Bedeutung / Regel |
|---|---|
| **AF-01 · `annotations[]`** | **Genau ein** Profil je Abgabe-Graphknoten, Ziel `{side:"submission", id, kind}` mit **Original-ID**. Bei zugeordnetem Objekt: `referenceId`, `mappingReason`, optionale `dependencies`. |
| **AF-02 · `identity`** | Identitätsstatus und relevante Kriterien (`method`, `role`, `result`, ggf. Kinderzähler und Abhängigkeiten). Nicht geprüfte/nicht anwendbare Kriterien werden in der kompakten Liste ausgelassen. |
| **AF-03 · `facts[]`** | Pro Fakt `id`, `code`, `status`, beteiligte IDs und kompaktes `evidence`; keine duplizierten Vollbeobachtungen, Endpunktblöcke oder Identitätskriterien. |
| **AF-04 · `hints[]`** | Für `violated` und `unresolved`: maschinenlesbarer Hinweis, `factId`, `scope` und konkrete `targets`. Gemeinsame Positionsbefunde können über `findingId` zusammengefasst werden. |
| **AF-05 · `referenceHints[]`** | Unzugeordnete Referenzobjekte: Anzeige möglichst am schon identifizierten Parent/Verbindungsendpunkt, andernfalls am Modell. `unmatched` ist **nicht** automatisch `missing`. |
| **AF-06 · `connectionGroups[]`** | Gruppenbefunde separat zu einzelnen Verbindungen; `groupIds` verweisen aus Objektannotation darauf. Ein Gruppenfehler belegt nicht die individuelle Schuld jeder Linie. |
| **AF-07 · Zusatzkontext** | `owner`, `containment`, `connection` aus vorhandenen Matcher-Beobachtungen, soweit für konkrete Ziele verfügbar. Strukturelle Hilfscontainer bleiben annotierbar. |

### Statuslogik für die Anzeige

```text
Identität: uniquely_supported | supported | unresolved
Fakt:      satisfied | violated | unresolved | not_evaluated | not_applicable
```

**AF-08 · Keine Vermischung:** `uniquely_supported` bedeutet **wiedererkannt**, nicht insgesamt korrekt. Ein Element kann zugleich `label.equal: satisfied` und `owner.*: violated` besitzen. Das aktuelle Format erzeugt **keinen einzigen Gesamtstatus pro Objekt** als Ersatz für diese Fakten.

**AF-09 · Beweisbasis:** Fakthinweise übernehmen `direct_observation`, `independent_evidence` oder `conditional_mapping` aus dem Matcher; die Feedbackschicht erfindet keine neue Gewissheit.

## 2. Dynamische Erkennungsübersicht – verbindliche Regel

**Quelle:** ausschließlich Referenzobjekte der jeweiligen Musterlösung. Keine festen Pflichtkategorien `nodes`/`attributes`/`connections`.

| Regel | Umsetzung |
|---|---|
| **AF-10 · Gruppierung** | Bei **eindeutiger expliziter `comparisonGroup`**: Referenzinstanzen derselben Gruppe zusammen; sonst **eine Zeile je konkretem Typ**. Schlüssel enthält Modellsprach-ID, Sprachversion und Objektart; keine gemischten Arten. |
| **AF-11 · Sichtbare Zeilen** | Nur tatsächlich in der Musterlösung vorkommende Gruppen/Typen; kein Platzhalter für 0 Referenzobjekte. Überlappende/uneindeutige Gruppen werden nicht transitive vereinigt. |
| **AF-12 · Was zählt als erkannt?** | Nur **ausgewählte 1:1-Paare** mit Matcher-Fakt `identity.status = uniquely_supported`, erfülltem `identity_anchor` **jenseits bloßer Typkompatibilität** und gültiger nicht zirkulärer Abhängigkeit. `supported` zählt nicht. |
| **AF-13 · Quote** | Pro Bucket: `recognized`, `expected`, `percent = 100 × recognized / expected`, `evaluationStatus`. Der Nenner ist die **ganze** Referenzmenge der Zeile; teilweise auswertbar heißt `partial`, nicht kleinerer Nenner. |
| **AF-14 · Leere / nicht auswertbare Bereiche** | Bei `not_evaluated`/`not_applicable` `percent: null`, nicht `0 %`. Gesamtwerte sind die Summen der Bucket-Werte. |
| **AF-15 · Zusätzliche Abgabeobjekte** | `unmatchedSubmission[]` separat führen; sie erhöhen den Erkennungszähler nicht und verschwinden bei 100 % Erkennung nicht. |
| **AF-16 · Strukturelle Hilfsobjekte** | `structuralElement` und `connectionLabel` zählen **nicht** als eigenständige Erkennungsobjekte, können aber Annotationen erhalten. `structuralContainers` zählt Container separat. |

**Hinweis zur heutigen Codegrenze:** `recognition_bucket()` schließt zwar `structuralElement`, `connectionLabel` und `comparisonRole: structural` aus; für sonstige ungewöhnliche `kind`-Werte ist der tatsächliche Einschluss nicht auf die zwei regulären Arten `modelElement` und `connection` begrenzt. Bei neuen Sprachen/Null-Arten gesondert testen, nicht stillschweigend als vollständig behoben dokumentieren.

## 3. Ausgabe für verschiedene Empfänger

```text
analysis-feedback/v3
  recognition: {basis, buckets[], overall, unmatchedSubmission[]}
  annotations[]:   {target, referenceId?, mappingReason?, identity?, facts[], hints[], ...}
  referenceHints[]: [{referenceId, kind, target, facts[], ...}]
  connectionGroups[]: [{id, referenceIds[], submissionIds[], facts[], ...}]
  structuralContainers: {referenceCount, submissionCount}
  status: provisional
  assessmentAvailable: false
```

- **AF-17 · Herkunft:** Vergleichs- und Analysehash, `analysisKey` und tatsächlicher Pfad müssen zusammenpassen; Veröffentlichung immutable/atomar.
- **AF-18 · Frontend-Transport:** Vollständiges **kompaktes** JSON bleibt ausdrücklich auf `stdout`, da der Dagu-Artefaktzugriff benötigt wird. Nicht durch reine Statuslogs ersetzen.
- **AF-19 · Berechtigungen:** Detaillierte Analysen/Referenzdaten sind in der vorgesehenen API nur für Moderation/Administration; die studentische Übersicht darf keine geschützten Referenznamen oder Rohdiagnosen offenlegen. Die API selbst liegt außerhalb dieses ZIPs und wird hier nicht neu verifiziert. **Ausnahme als Probe (seit 24.11.2026):** `labelHints[].suggestion` darf den Text des Musterlösungselements enthalten, solange `comparisonConfig.graphMatching.hints.showReferenceText` gesetzt ist. Die Probe zeigt, wie oft das vorkommt; danach wird festgelegt, was angezeigt werden darf.
- **AF-21 · Hinweise:** `labelHints` projiziert die Matcher-Hinweise (GM-43) mit Abgabebeschriftung, Quellen und Wortteilbeziehung. Der Validator rechnet sie aus dem Vergleich nach. Sie stehen außerhalb von `recognition` und zählen nie. Analysen zu Vergleichen ohne `hints` haben das Feld nicht.
- **AF-20 · Feedback Generation:** Übernimmt den validierten Bericht bzw. dessen dynamische Erkennungsdaten. Das ist **kein zweiter** Ort zur Neuberechnung der Wiedererkennung.

## Grenzen und ausdrücklich **nicht** hier lösen

- Kein zweiter Graph-Matcher, keine nachträgliche Identitätsförderung anhand hübscher Indikatoren.
- Keine semantischen Wahrscheinlichkeiten aus Cosinuswerten ableiten; nur **tatsächlich verwendete** Matcher-Evidenz darstellen.
- Eine unzugeordnete Referenzinstanz nur bei Matcherbeweis als `reference.missing`, sonst `reference.unresolved`.
- Die Ausgabe ist **keine Benotung**. `status: provisional`, `assessmentAvailable: false`.

## Änderungslandkarte

| Bereich | Maßgebliche Stelle |
|---|---|
| Fakten → Objektannotation/Hinweise | `dagu/workflow-services/analytical-feedback/src/fact_projection.py` · `build_evidence_report()` |
| Erkennung, dynamische Buckets, Validierung, kompakte Felder | `analytical-feedback/src/analysis_contract.py` · `recognized_reference_ids()`, `recognition_bucket()`, `recognition_summary()`, `compact_fact()`, `compact_identity()`, `validate_current_analysis()` |
| Hauptaufruf, Hashkette, Speicher-/stdout-Transport | `analytical-feedback/src/main.py` |
| Orchestrierung + Übergabe | `dagu/workflows/model-evaluation-graph-matching.yaml` · `analytical-feedback-pair` |
| Feedback-Weitergabe | `dagu/workflow-services/feedback-generation/src/main.py` |
| Tests | `analytical-feedback/tests/` |

**Änderungsregel:** Jede neue Diagramm-Anzeigeaussage muss sich auf einen existierenden Matcher-Fakt zurückführen lassen. Fehlt dieser, zunächst eine Matcher-Anforderung formulieren – nicht die Auswertung im Feedbackdienst nachbauen.
