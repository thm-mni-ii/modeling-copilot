# 04 – Semantische Kandidaten für ein Modellpaar liefern

**Baustein:** Container und Implementierungsordner `synonym-matching`; interner Workflow `synonym-matching-pair`.

**Abhängigkeit:** [03 – Elementinventar](03-model-label-extraction.md). Es gelten die [gemeinsamen Verträge](README.md).

**Stand:** Paket 04 ist im Zielordner `synonym-matching` implementiert und
ausschließlich statisch durchgesehen. Der [Servicevertrag](../../dagu/workflow-services/synonym-matching/README.md)
beschreibt die tatsächlichen V1-Ein-/Ausgaben, Methoden und Ressourcen. Keine neuen
fachlichen Konfigurationsparameter und kein Laufzeitnachweis.

## Arbeitsziel

Für genau eine Referenz und die Abgabe wird die vollständige semantische Kandidatenevidenz erzeugt. Das Ergebnis lässt sich unmittelbar mit den zugehörigen Graphen verbinden und enthält genügend Informationen, damit der strukturelle Matcher konkurrierende Kandidaten selbst beurteilen kann.

**Verbindliche Arbeitsgrenze:** Die Workflow-Implementierung entsteht unter `dagu/workflow-services/synonym-matching/`. Der Ordner `dagu/workflow-services/synonym-matching-louis/` ist ausschließlich eine lesbare Methodenreferenz und wird nicht verändert. Benötigte Methoden und unterstützende Codeteile dürfen daraus in den eigenen Implementierungsordner kopiert und dort angepasst werden. Es werden keine Workflow-Adapter, Schemaänderungen, Docker-Anpassungen, Tests oder sonstigen Ergänzungen im Referenzordner vorgenommen.

Der fertige Workflow-Container verwendet seinen eigenen Code, seine eigenen Schnittstellen und seine eigene Build-Konfiguration. Er importiert zur Laufzeit keine Module aus dem Referenzordner und benötigt weder dessen Quellverzeichnis als Mount noch einen `sys.path`-Umweg oder dessen Image als ausführenden Workflow-Service. Die Herkunft übernommener Methoden bleibt in der eigenen Dokumentation nachvollziehbar.

## Ausgangslage und relevante Stellen

- [main.py im Zielordner](../../dagu/workflow-services/synonym-matching/src/main.py): CLI-/Workspace-Einstieg in die implementierte Kandidatenberechnung.
- [Methodenreferenz](../../dagu/workflow-services/synonym-matching-louis/src/synonym_matching/methods.py): vorhandene Ähnlichkeitsverfahren als Grundlage für die Übernahme in eigene Methodenmodule.
- [service.py der Referenz](../../dagu/workflow-services/synonym-matching-louis/src/synonym_matching/service.py): Ablauf, Einzelmatrizen und Kandidatenaufbau als Orientierung.
- [config.py der Referenz](../../dagu/workflow-services/synonym-matching-louis/src/synonym_matching/config.py): dokumentierte Ausgangskonfiguration als Orientierung.
- [combinations.py der Referenz](../../dagu/workflow-services/synonym-matching-louis/src/synonym_matching/combinations.py): Rechenregeln und Behandlung der Scoreskalen als Grundlage für die eigene Kombination.

Der frühere Platzhalter `synonym-matching` ist durch den Workflow-Service ersetzt. Die vier dokumentierten Verfahren sind in eigene Methodenmodule übernommen. Die Implementierung liegt eigenständig im Zielordner; sie importiert keine Laufzeitquellen aus der Methodenreferenz. Ein breiter neuer Vergleich von Sprachmodellen ist kein Bestandteil dieses Arbeitspakets.

## Aufbau innerhalb des Zielordners

Die Verantwortungen werden in überschaubare Module aufgeteilt. Jede eingesetzte Ähnlichkeitsmethode besitzt ein eigenes Methodenmodul. Vorverarbeitung, Kombination und Workflow-Ein-/Ausgabe bleiben davon getrennt. Eine mögliche, an den tatsächlichen Bedarf anzupassende Struktur lautet:

```text
synonym-matching/
  Dockerfile
  README.md
  requirements.txt             # tatsächlich benötigte Abhängigkeiten des eigenen Containers
  schemas/                     # eigene Ein-/Ausgabe, soweit für die Schnittstelle benötigt
  src/
    main.py                    # Einstieg: Eingabe lesen, Ablauf aufrufen, Ergebnis veröffentlichen
    synonym_matching/
      service.py               # Ablauf für ein Modellpaar, Matrizen und Kandidaten zusammenführen
      config.py                # tatsächlich benötigte Konfiguration und deren Prüfung
      preprocessing.py         # gemeinsame Textvorbereitung
      combinations.py          # Einzelwerte nachvollziehbar kombinieren
      methods/
        levenshtein.py
        jaro_winkler.py
        char_trigram.py
        multilingual.py
```

Diese Struktur schreibt kein Plugin-Framework, keine Klassenhierarchie und keine Datei für jede Hilfsfunktion vor. Gemeinsame Hilfsfunktionen oder Ressourcenlader werden nur bei tatsächlicher Wiederverwendung ausgelagert. Weitere übernommene Methoden werden nach demselben Prinzip nachvollziehbar eingeordnet. Unbenötigte Forschungsrunner, Testdaten und Testinfrastruktur werden nicht mitkopiert.

`main.py` darf die Verarbeitung sinnvoll zusammenführen, hält aber weder sämtliche Algorithmen noch sämtliche Validierungs-, Vorverarbeitungs- und Kombinationsregeln in einer einzigen großen Datei. Einzelmethoden berechnen Ähnlichkeiten; sie kennen keine Workspace-Pfade, Auswertungs-IDs oder Dagu-Aufrufe.

## Fortsetzung nach einem abgebrochenen Umsetzungsversuch

Vor der Fortsetzung den vorhandenen Arbeitsstand ausschließlich lesend zuordnen. Bereits vorhandene Änderungen oder neu angelegte Workflow-Dateien im Referenzordner sind keine Freigabe für weitere Bearbeitung dort. Benötigte fachliche Methoden und brauchbare Workflow-Anteile werden nur in den Zielordner übernommen; unvollständige Adapter nicht ungeprüft als fertigen Methodenbestand behandeln.

Keine pauschalen Restore-, Checkout- oder Reset-Aktionen durchführen: Änderungen
können unabhängig entstandene Arbeit enthalten. Für diese Fortsetzung hat der Nutzer
die gezielte Wiederherstellung der eigenen Eingriffe ausdrücklich beauftragt.
Der anfängliche Git-Status zeigte keine Änderungen im Referenzordner; die späteren
Diffs entsprachen den protokollierten Eingriffen. Zurückgenommen wurden Änderungen
an `Dockerfile`, `capability.yaml`, beiden Schemas, `src/main.py`,
`src/synonym_matching/methods.py` und `service.py`; die neu angelegte
`src/synonym_matching/workflow.py` wurde entfernt. Danach zeigt Git dort keine
Reständerungen. Dies belegt den nachvollziehbaren Arbeitsstand, keinen darüber
hinausgehenden Dateisystem-Snapshot. Seit der Wiederherstellung wird der Ordner
ausschließlich lesend verwendet.

## Was kommt hinein?

| Eingang | Inhalt |
|---|---|
| `WORKFLOW_EVALUATION_ID` | Laufbezug |
| `REFERENCE_KEY` | Eine erwartete Referenz aus dem Snapshot |
| Abgabeinventar | `labels/submission.json` |
| Referenzinventar | `labels/<referenceKey>.json` |
| Konfiguration | `comparisonConfig.semantics` aus dem Snapshot |
| `WORKFLOW_OUTPUT_PATH` | `candidates/<referenceKey>.json` |

Der Schritt prüft Quelle, Schema und Graph-/Inventarbezug. Im eigenständigen Aufruf können dieselben beiden kompakten Inventare und dieselbe Konfiguration als JSON übergeben werden. Der Matching-Kern benötigt daraus IDs, Textstatus und `matchText`; Originaldaten und Modellsprachreferenzen bleiben im referenzierten Graphen. Nur `textLanguage` bezeichnet eine natürliche Sprache, beispielsweise `de`; aus einer Modellsprachreferenz wird keine natürliche Sprache abgeleitet.

**Tatsächlicher Aufrufvertrag:** Der Workspace-Aufruf liest die beiden genannten
Inventardateien direkt. `REFERENCE_KEY` und `WORKFLOW_OUTPUT_PATH` sind erforderlich;
der Ausgabedateiname muss `<REFERENCE_KEY>.json` sein. `WORKFLOW_INPUT_PATH`,
`TEMPLATE_INPUT` und `--input` sind in diesem Modus keine Eingabealternativen.
Eigenständig wird ein Objekt mit `studentInventory` und `referenceInventory`
(jeweils vollständige erfolgreiche Inventarhüllen aus Paket 03) sowie optionalem
`comparisonConfig` gelesen: `--input`, `TEMPLATE_INPUT` oder stdin; Ausgabe über
stdout beziehungsweise `--output`. Ohne Workspace erfolgt kein externer
Snapshot-Abgleich. Inventarhashes, gegenseitiger Lauf-/Inputbezug und Rollen werden
immer geprüft; im Workspace zusätzlich die vollständigen Quellen des Snapshots.
Graphhashes werden erhalten; Paket 05 gleicht sie mit seinen Graphen ab.

`comparisonConfig: {}` genügt. `semantics` darf fehlen oder leer sein; nicht leere
oder falsch typisierte semantische Einstellungen werden erklärt abgewiesen. Andere
Bereiche bleiben ihren zuständigen Schritten vorbehalten. Es werden weder
Methodenauswahl noch Aliasregeln oder Filterparameter neu eingeführt.

## Was kommt heraus?

Eine `workflow-result/v1`-Hülle mit `capability: synonym-matching` und:

| Feld in `result` | Inhalt |
|---|---|
| `schema` | `semantic-candidates/v1` |
| `evaluationId`, `pair` | Lauf und Modellschlüssel beider Seiten; Modellquellen stehen in den referenzierten Inventaren und im Snapshot |
| `graphHashes`, `inventoryHashes` | Jeweils `student` und `reference` |
| `inputHash`, `inventoryPaths` | Gemeinsamer Snapshot-Bezug und relative Inventarpfade unter `student` und `reference` |
| `semanticConfigHash`, `producer` | Tatsächlich verwendete Konfiguration und Ressourcenrevisionen |
| `semanticConfig`, `processedTexts`, `evaluatedPairCount` | Aufgelöste Konfiguration, tatsächliche Methodentexte je ID und Zahl berechneter Paare |
| `candidateHash` | Hash der vollständigen Kandidatenevidenz und ihrer Eingabebezüge |
| `methods` | Berechnete Verfahren, Wertebereiche und Beteiligung an der Kombination |
| `combiner`, `threshold`, `filtered` | Rechenregel und Aussage zur Vollständigkeit der Kandidaten |
| `synonymMatrix` | Eine Zeile je `referenceElementId`, darin Kandidaten mit `submissionElementId` und unveränderten Scores |
| `unscoredElements` | Elemente ohne verwendbaren Text samt Seite, ID und Grund |
| `diagnostics` | Nur eigene Hinweise; vorgelagerte Diagnosen bleiben in ihren referenzierten Artefakten |
| `completeness` | Technisch vollständig bei Erfolg; Interpretation aus beiden Inventaren erhalten |

Die Matrix enthält Original-IDs statt vollständiger Elementdaten. IDs werden im Kontext von `evaluationId` und `pair` aufgelöst; Inventare verweisen wiederum über `graphPath` und `graphHash` auf Originalknoten und Labels. Vollständige Inventare, Modellquellen und vorgelagerte Diagnosen werden nicht erneut eingebettet. Auch eigenständige Aufrufer bewahren die Eingabeartefakte separat unter den referenzierten Pfaden auf; der Standard für Inventare ist `labels/<modelKey>.json`.

Beispielausschnitt mit illustrativen, nicht gemessenen Scores:

```json
{
  "schema": "semantic-candidates/v1",
  "evaluationId": "evaluation-1",
  "pair": { "studentKey": "submission", "referenceKey": "reference_1" },
  "inventoryPaths": { "student": "labels/submission.json", "reference": "labels/reference_1.json" },
  "graphHashes": {
    "student": "sha256:student-graph",
    "reference": "sha256:reference-graph"
  },
  "inventoryHashes": {
    "student": "sha256:student-inventory",
    "reference": "sha256:reference-inventory"
  },
  "threshold": null,
  "filtered": false,
  "synonymMatrix": [
    {
      "referenceElementId": "r5",
      "matches": [
        {
          "submissionElementId": "s5",
          "scores": {
            "levenshtein": 0.14,
            "jaro_winkler": 0.43,
            "char_trigram": 0.0,
            "multilingual": 0.78
          },
          "combinedScore": 0.485,
          "aliasEvidence": []
        }
      ]
    }
  ],
  "unscoredElements": [],
  "diagnostics": []
}
```

Weitere Matrixzeilen sowie Quellen-, Methoden- und Hashmetadaten sind ausgelassen. Im vollständigen Artefakt bleiben auch die Kandidaten für `E-Mail` und alle anderen verwendbaren Labelpaare erhalten. Ein Referenzelement ohne Text besitzt eine leere Matrixzeile und einen Eintrag in `unscoredElements`; es verschwindet nicht.

## Umgesetzter Arbeitsumfang

1. **Methoden in den eigenen Service übernehmen.** Die benötigten Algorithmen und unterstützenden Rechenregeln aus der unveränderten Methodenreferenz nach `synonym-matching` übernehmen. Jede eingesetzte Methode nachvollziehbar trennen; gemeinsamen Ablauf und Kombination im eigenen Paket zusammenführen. Keine laufende Quellcode-Abhängigkeit vom Referenzordner schaffen.
2. **Workflow-Grenze im Zielordner ergänzen.** Inventare und Konfiguration aus dem bestehenden Workspace lesen; die eigenen Methodenmodule über den eigenen Ablauf mit IDs und Vergleichstexten aufrufen; Resultate wieder mit Originalquellen verbinden. `main.py` bleibt ein überschaubarer Einstieg. Der fachliche Kern benötigt weder Dagu- noch Datenbankzugriff. Dockerfile, benötigte Abhängigkeiten und eigene Schnittstellen ausschließlich im Zielordner anpassen; bereits vorhandene technische Workflow-Metadaten auf `synonym-matching` ausrichten, soweit sie diesen Schritt direkt betreffen.
3. **Vorläufigen Standard explizit übernehmen.** Die Referenz dient als Ausgangspunkt für Levenshtein, Jaro-Winkler, Zeichen-Trigramme und das multilinguale Embedding mit 50:50-Gewichtung zwischen Stringmittel und Embedding. Berechnungen und Vorverarbeitung bei der Übernahme nicht still verändern. Die tatsächlich aufgelöste Modellrevision wird in der eigenen Ausgabe dokumentiert. Benötigte Modellressourcen sind beim späteren Lauf im eigenen Container verfügbar; kein ungeplanter Download pro Modellpaar.
4. **Originale und Verarbeitung erhalten.** Verwendete Texte, Vorverarbeitung und natürliche Sprache nachvollziehbar halten. Keine stillen Übersetzungen oder aggressiven Normalisierungen. Unbekannte natürliche Sprache darf beim multilingualen Standard offenbleiben; Verfahren mit zwingender Sprachangabe dürfen sie nicht erraten.
5. **Vollständige Evidenz ausgeben.** Die interne Ausgabe verwendet `threshold: null`, `filtered: false` und keine Top-1-/Top-k-Reduktion. Alle konfigurierten Einzelverfahren werden erhalten, einschließlich nicht in die Kombination eingehender Verfahren. Endliche Rohwerte werden für maschinelle Nachfolger nicht auf vier Stellen gerundet.
6. **Skalen dokumentieren.** Cosinuswerte können negativ sein; die übernommene Kombination begrenzt ihre Beiträge auf `[0,1]`. Rohwert und Kombinationsbeitrag dürfen nicht verwechselt werden. `combinedScore` ist ein Ähnlichkeitswert und keine Wahrscheinlichkeit.
7. **Keine unbenötigten Aliasparameter einführen.** Der übernommene Standard benötigt kein aufgabenbezogenes Aliaswissen. `aliasEvidence` bleibt leer; spätere Regeln erfordern eine gesonderte Konkretisierung einschließlich Eingabedokumentation.
8. **Instanzen getrennt halten.** Gleicher Text kann berechnungsintern wiederverwendet werden. Die Ausgabe führt dennoch jede Element-ID separat. Leere Texte werden als nicht auswertbar markiert, nicht als ähnliches Paar behandelt.
9. **Ressourcengrenzen offenlegen.** Das Modell-Tokenlimit wird vor dem Encoding geprüft, ohne Texte still abzuschneiden. Ein numerisches Paarlimit ist bislang nicht vereinbart und wird nicht erfunden. Die vollständige Matrix wächst mit dem Produkt der Inventargrößen; Speicherfehler bleiben technische Fehler. Konkrete Betriebsgrenzen werden mit Paket 07 festgelegt, ohne heimliche Kandidatenkürzung.

Das Modell ist auf Revision `e8f8c211226b894fcb81acc59f3b34ba3efd5f42` von
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` festgelegt. Der eigene
Container bereitet nur dieses vorhandene Standardmodell vor. Paaraufrufe laden
ausschließlich lokal verfügbare Ressourcen und verhindern einen automatischen
Ersatz durch eine andere Pooling-Pipeline. Bei fehlenden verwendbaren Paaren wird
kein Modell geladen; der Ressourcenbericht benennt dies mit `resolvedRevision: null`
und `not_needed_no_usable_pairs`. Eigener Code-/Schemahash, tatsächliche
Paketversionen und verwendete Modellrevision werden dokumentiert.

Für initiale Containeraufrufe dürfen unterschiedliche Elementtypen semantisch verglichen werden. Eine Typ- oder Containerabweichung ist hier kein harter Filter; deren fachliche Behandlung erfolgt im strukturellen Schritt.

## Fehlerverhalten

Ein fehlendes erforderliches Modell, ein ausgefallenes konfiguriertes Verfahren, ungültige Scorewerte oder widersprüchliche Eingabebeziehungen verhindern ein reguläres Kandidatenartefakt. Es gibt im initialen Standard keinen stillen Rückfall auf ein anderes Verfahren oder andere Gewichte. Ein vollständig leeres Inventar ergibt hingegen eine gültige leere beziehungsweise zeilenweise leere Matrix.

Eine im Inventar gemeldete Interpretationslücke bleibt erhalten. Sie bedeutet nicht automatisch, dass lesbare Labels überhaupt nicht verglichen werden dürfen; der spätere Matcher erfährt aber die Einschränkung.

## Erfüllungskriterien

**Statisch durchgesehen:** Die Häkchen bezeichnen implementiertes Verhalten,
keinen Test- oder Laufzeitnachweis.

- [x] Der Workflow-Service und seine eigene Build-/Schnittstellenkonfiguration liegen unter `synonym-matching`; die Capability heißt `synonym-matching`.
- [x] Der Methodenreferenzordner wurde gezielt auf den nachvollziehbaren Ausgangsstand wiederhergestellt und ist keine Laufzeit- oder Build-Quellcodeabhängigkeit.
- [x] Jede eingesetzte Ähnlichkeitsmethode liegt in einem eigenen Methodenmodul; Vorverarbeitung, Kombination, Paarablauf und CLI-Einstieg sind getrennt.
- [x] Ein Aufruf verarbeitet genau das angegebene Modellpaar und erhält dessen vollständige Herkunft.
- [x] Alle verwendbaren Labelpaare bleiben mit Einzelwerten und dokumentiertem kombinierten Wert verfügbar.
- [x] Gleiche Labels mit unterschiedlichen IDs sowie konkurrierende Kandidaten bleiben getrennt erhalten.
- [x] Fehlende Texte sind ausdrücklich bezeichnet und bleiben Teil des Inventars.
- [x] Der Service liefert keine endgültige One-to-One-Zuordnung.
- [x] Graph-/Inventarhashes, Konfiguration und Ressourcenrevisionen sind für Paket 05 dokumentiert.
- [x] Methodenausfälle, ungültige Werte und Tokenlimitüberschreitungen verhindern ein neues Erfolgsartefakt; kein stiller Ersatz oder Kandidatenverlust.

**Aktuelle Verifikation:** Ausschließlich statische Durchsicht der Änderungen und Schnittstellen. Keine Tests erstellen, erweitern oder ausführen; keine manuellen Modell-/Containerläufe, Builds, Benchmarks, Lint- oder Syntaxprüfungen. Die Kriterien beschreiben Sollverhalten und sind derzeit kein Auftrag zur Ausführung.

**Übergabe:** [05 – One-to-One-Graph-Matching](05-one-to-one-graph-matching.md) liest die vollständige Kandidatenevidenz zusammen mit genau den referenzierten Graphen.

**Offen:** Gesondert beauftragte Laufzeitverifikation, semantische Qualität auf
realen Abgaben, konkrete betriebliche Paar-/Speichergrenzen und die Folgepakete
05/06 sowie deren Integration in 07/08. Die Verkabelung und JSON-Anzeige bis Phase 4
sind vorhanden; die aktuellen kompakten Verträge wurden nicht zur Laufzeit geprüft.

## Kontrollauftrag für den implementierten Stand

```text
Prüfe den implementierten Stand von Arbeitspaket 04 anhand der aktualisierten
docs/model-comparison-work-packages/04-synonym-matching.md und korrigiere nur
konkrete Abweichungen vom dort beschriebenen Vertrag. Die Methodenübernahme
und Workflow-Anbindung bis Phase 4 sind abgeschlossen.

Die frühere Anweisung, den Referenzordner direkt als Workflow-Service anzupassen,
ist aufgehoben. Implementiere ausschließlich im Zielordner
dagu/workflow-services/synonym-matching/ und dessen unmittelbar notwendiger Anbindung.

dagu/workflow-services/synonym-matching-louis/ ist nach der ausdrücklich
beauftragten, gezielten Wiederherstellung nur eine lesbare Methodenreferenz.
Die Wiederherstellung ist abgeschlossen und darf nicht pauschal wiederholt werden.
Benötigte Methoden und unterstützenden Code darfst du in den Zielordner kopieren
und dort anpassen. Keine Laufzeitimporte, Quellcode-Mounts oder Build-Abhängigkeit
vom Referenzordner. Neue unabhängige Änderungen dort bleiben erhalten.

Trenne jede eingesetzte Methode in ein überschaubares Methodenmodul. Halte
Vorverarbeitung, Kombination, Paarablauf und Workflow-Ein-/Ausgabe nachvollziehbar
auseinander. main.py bleibt der schlanke Einstieg und führt den Ablauf zusammen;
kein unnötiges Plugin-Framework und keine große Datei mit sämtlichen Algorithmen.

Erhalte die allgemeinen kompakten V1-Ein-/Ausgaben: inventoryPaths/inventoryHashes
referenzieren die Inventare; referenceElementId und submissionElementId benennen
Original-IDs im Modellpaar. Vollständige Knoten, Inventare und vorgelagerte Diagnosen
nicht erneut einbetten. Alle berechneten Paarwerte, Methoden und Gewichte bleiben
erhalten. Die Capability heißt synonym-matching.
Keine sprachspezifischen Sonderfälle und noch kein strukturelles Matching oder Feedback.

Keine Tests erstellen, erweitern oder ausführen. Keine Probeläufe, Containerstarts,
Builds, Benchmarks, Modell-Erprobungsdownloads, Lint- oder Syntaxprüfungen.
Nur lesen, bearbeiten und statisch durchsehen. Andere Nutzeränderungen bewahren.

Fasse am Ende die Änderungen im Zielordner, die übernommenen Methoden und offene
Restpunkte zusammen. Stelle ausdrücklich fest, dass nichts getestet wurde und der
Referenzordner seit der dokumentierten Wiederherstellung nicht weiter verändert wurde.
```
