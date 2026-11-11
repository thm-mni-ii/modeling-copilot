# 05 – Ein Modellpaar zuordnen und strukturelle Befunde erzeugen

**Baustein:** Container `one-to-one-graph-matching`; geplanter interner Workflow `one-to-one-graph-matching-pair`.

**Abhängigkeiten:** [02 – Graphen](02-graph-parser.md) und [04 – semantische Kandidaten](04-synonym-matching.md). Es gelten die [gemeinsamen Verträge](README.md).

**Stand:** Geplant; der vorhandene Container ist ein Platzhalter. Die aktualisierten Eingabereferenzen aus 02–04 sind dokumentiert, der folgende Ergebnisvertrag und Matchingalgorithmus noch nicht implementiert.

## Arbeitsziel

**Aktualisierte Übergabe aus 02–04:** Inventare und Kandidaten referenzieren ihre Eingaben, statt vollständige Vorgängerergebnisse zu kopieren. `inventoryPaths`/`inventoryHashes` benennen die Inventare im selben Lauf; diese verweisen mit `graphPath`/`graphHash` auf die Graphen. Matrixzeilen verwenden `referenceElementId`, Kandidaten `submissionElementId`. Der geplante Matcher liest Originalknoten und vorgelagerte Diagnosen aus diesen Artefakten. `contains` besitzt keine eigene ID oder Herkunftskopie; Besitzerpfade werden anhand von Quelle/Ziel und Originalknoten nachvollzogen. Anschlusskanten behalten ihre Herkunft und Ports. Diese Vertragsaktualisierung implementiert keinen Matchingalgorithmus.

Die Abgabe wird gegen genau eine vollständige Referenz verglichen. Das Ergebnis enthält belastbare partielle One-to-One-Zuordnungen, offene Konkurrenzgruppen und daraus abgeleitete Unterschiede an Elementen, Beziehungen und Zugehörigkeiten.

Zuordnung und Befundbildung gehören in diesem Paket zusammen. Sie sind getrennte fachliche Verantwortungen innerhalb desselben Containers; ein weiterer Dienst nur für Befunde ist nicht erforderlich.

## Ausgangslage und relevante Stelle

[one-to-one-graph-matching/main.py](../../dagu/workflow-services/one-to-one-graph-matching/src/main.py) ist derzeit ein Platzhalter. Der im [Gesamtkonzept](../model-comparison-pipeline-concept.md) beschriebene partielle globale Abgleich wird hier erstmals umgesetzt. Parser- und Semantiklogik werden nicht dupliziert.

## Was kommt hinein?

| Eingang | Inhalt |
|---|---|
| `WORKFLOW_EVALUATION_ID`, `REFERENCE_KEY` | Lauf und genau eine erwartete Referenz |
| Abgabegraph | `graphs/submission.json` |
| Referenzgraph | `graphs/<referenceKey>.json` |
| Kandidaten | `candidates/<referenceKey>.json` |
| Regeln | Bei tatsächlichem Bedarf definierte allgemeine `comparisonConfig.matching`-/`comparisonConfig.selection`-Einstellungen und die erhaltenen Sprachdefinitionen; kein sprachspezifisches Parserprofil |
| `WORKFLOW_OUTPUT_PATH` | `comparisons/<referenceKey>.json` |

Vor der Verarbeitung müssen Graphhashes, Quellen, Paarbezug, Profile und Konfigurationsbezüge übereinstimmen. Eine gefilterte Kandidatenmatrix ist für diesen initialen Vertrag keine vollständige Eingabe.

## Was kommt heraus?

Eine `workflow-result/v1`-Hülle mit `capability: one-to-one-graph-matching` und:

| Feld in `result` | Inhalt |
|---|---|
| `schema` | `reference-comparison/v1` |
| `evaluationId`, `inputHash`, `pair`, `sources` | Lauf, Eingabesnapshot, Paar und vollständige Originalmodellquellen |
| `graphHashes`, `candidateHash`, `matchingConfigHash`, `producer` | Verwendete Verarbeitungsversionen und Eingaben |
| `mapping` | Bestätigte Element- und Beziehungszuordnungen mit Kriterien und Evidenz |
| `unresolvedGroups` | Betroffene Instanzen, mögliche Entsprechungen, Gründe und Abhängigkeiten |
| `findings` | Korrekte, abweichende, falsch zugehörige, fehlende oder zusätzliche Bestandteile |
| `coverage` | Vollständige fachliche Element-/Beziehungs-IDs beider Seiten; je Instanz der Zustand zugeordnet, ungeklärt, fehlend/zusätzlich oder nicht interpretierbar |
| `comparisonUnits` | Einmalig gezählte fachliche Vergleichseinheiten für Paket 06 |
| `completeness` | Technische Abdeckung, Interpretation und Zuordnungsabdeckung |
| `diagnostics` | Eigene Matching-/Interpretationsprobleme mit Evidenzreferenzen; Parser- und Semantikdiagnosen bleiben in den referenzierten Eingabeartefakten |
| `assessmentAvailable` | Initial immer `false` |

`mapping` verwendet ausschließlich `status: matched` für ausreichend gestützte Identitätsentscheidungen. Korrektheit oder Fehlplatzierung steht in den Befunden. Ein Element kann passend identifiziert sein und zugleich eine falsche Eigenschaft oder Zugehörigkeit haben.

## Geplanter Arbeitsumfang

### 1. Globales Kandidatenfeld und Kriterien

Alle fachlichen Elemente bleiben über sämtliche Container hinweg erreichbar. Unterschiedliche Besitzer, Typdetails oder Knotengrade schließen ein Paar nicht pauschal aus. Harte Sperren benötigen eine dokumentierte Regel; technische Strukturknoten und fachliche Elemente werden nicht zu künstlichen Gegenstücken.

Das Startprofil aus dem Konzept verwendet folgende Kriterien:

| Kriterium | Vorgesehene Grundlage | Vorläufiges Gewicht |
|---|---|---:|
| Label `L` | Kombinierte semantische Evidenz; bestätigtes Aliaswissen separat ausweisen | 0,55 |
| Typ `T` | Gleichheit beziehungsweise ausdrücklich definierte Typverträglichkeit | 0,10 |
| Eigenschaften `P` | Anteil übereinstimmender, laut Profil vergleichbarer Eigenschaften | 0,10 |
| Nachbarschaft `N` | Beziehungstypen, Rollen und Richtung; im zweiten Durchgang zugeordnete Nachbarn | 0,20 |
| Container `C` | Vergleich wirksamer fachlicher Besitzer und Vorfahren gemäß Profil | 0,05 |

Die genaue Eigenschaftsauswahl und Typverträglichkeit stammen aus dem eingefrorenen Profil. Fehlende Evidenz ist nicht automatisch null oder eins. Nicht anwendbare Kriterien werden aus dem Nenner genommen und ihre Abwesenheit wird ausgewiesen. Zwei leere Nachbarschaften liefern keinen starken Identitätsnachweis.

Als initiale strukturelle Beschreibung können typisierte Nachbarschaftshäufigkeiten verglichen werden. Im Nachbewertungsschritt zählen insbesondere Beziehungen zu belastbar zugeordneten Nachbarn. Zugehörigkeit wird dabei nicht zusätzlich als normale Nachbarschaftsbeziehung doppelt gewichtet.

### 2. Evidenz vor einer Entscheidung verlangen

Ein hoher Zahlenwert allein genügt nicht. Eine bestätigte Zuordnung benötigt neben globaler Konkurrenzprüfung entweder:

- eine klare Labelentsprechung beziehungsweise bestätigtes Aliaswissen ohne fachlichen Widerspruch; oder
- zusammenpassende Text-/Typevidenz und einen unterscheidenden, unabhängig gestützten Strukturkontext.

Bei fehlenden Labels muss der Strukturkontext die Identität selbst ausreichend unterscheiden. Ein passender Typ und dieselbe Containergröße allein reichen dafür nicht. Dieses Evidenzprofil wird als Regelkonfiguration dokumentiert; die Werte sind keine kalibrierten Wahrscheinlichkeiten.

### 3. Partielles globales Assignment

Ein bipartites Assignment wählt unter konkurrierenden Paaren eine globale Zuordnung. Jede Instanz kann höchstens einmal vorkommen; beide Seiten besitzen eine Nichtzuordnungsoption. Der vorläufige `acceptThreshold` beträgt `0.70`; der Zuordnungsnutzen oberhalb dieser Schwelle wird gegenüber Nichtzuordnung betrachtet.

Nichtzuordnung ist zunächst eine algorithmische Entscheidung. Sie wird erst nach fachlicher Einordnung zu `missing`, `additional` oder `unresolved`.

### 4. Mehrdeutigkeit prüfen

Für vorgeschlagene Paare wird die beste Gesamtzuordnung ohne dieses Paar betrachtet. Unterscheidet sich deren Zielfunktionswert nur wenig, ist das Paar nicht ausreichend stabil. Die vorläufige `ambiguityMargin: 0.05` bezieht sich auf die Differenz dieser Zuordnungsnutzen, nicht auf eine Wahrscheinlichkeit.

Die betroffenen konkurrierenden Instanzen bilden eine offene Gruppe. Es wird keine fachliche Entscheidung durch zufällige Reihenfolge oder lexikografische ID-Auswahl getroffen. Reproduzierbare Sortierung betrifft ausschließlich die Ausgabe.

### 5. Genau ein struktureller Nachbewertungsschritt

Unabhängig ausreichend gestützte vorläufige Paare liefern Kontextanker. Mit ihnen werden Nachbarschaft und wirksamer Besitzer erneut verglichen und die globale Zuordnung einmal aktualisiert. Vorläufige Paare sind nicht unwiderruflich gesperrt.

Kriterien halten fest, auf welche Anker sie sich stützen. Wird ein Anker verworfen, können ausschließlich davon abhängige Paare nicht als gesichert bestehen bleiben. Zirkuläre Stützung erzeugt keine Evidenz. Nach dieser Prüfung endet die fachliche Iteration; verbleibende Unsicherheit wird ausgegeben.

Die alternativen Assignment-Berechnungen zur Mehrdeutigkeitsprüfung sind keine zusätzlichen semantisch-strukturellen Lernschleifen. Ihre Ressourcen zählen trotzdem gegen das vereinbarte Verarbeitungslimit.

### 6. Eigenschaften und Zugehörigkeiten vergleichen

- Identifizierte Elemente werden nach ihren vergleichbaren Eigenschaften beurteilt.
- Der fachliche Besitzer wird aus der erhaltenen `contains`-Kette ermittelt; ausschließlich ausdrücklich transparente Strukturfächer werden übersprungen.
- Eine falsche Zugehörigkeit ergibt `WRONG_OWNER` mit tatsächlichem Besitzer, erwarteter Referenzzugehörigkeit und den zugrunde liegenden Pfaden.
- Bei verschobenen Containern wird die abweichende Elternbeziehung am Container erfasst. Lokal richtige Kindbeziehungen werden nicht allein wegen des veränderten Vorfahren erneut als falsch behandelt.
- Ist ein Besitzer ungeklärt, bleibt auch der davon abhängige Besitzervergleich offen.

### 7. Beziehungen vergleichen

Beziehungsknoten werden über ihre Endpunkte, ihren Typ, Richtung, Labels, Rollen und Eigenschaften zugeordnet. Mehrere Beziehungen zwischen denselben Endpunkten bleiben getrennte Instanzen; auch für sie gilt höchstens ein Gegenstück.

Bei ungerichteten Beziehungen darf die Endorientierung einschließlich endbezogener Eigenschaften vertauscht werden. Bei unbekannter Richtung wird keine falsche Richtung behauptet.

Eine eindeutig erkennbare Beziehung mit falschem Typ oder Richtung erhält einen Abweichungsbefund. Sie wird nicht zusätzlich als vollständig fehlende und vollständig zusätzliche Beziehung ausgegeben. Bei ungeklärten Endpunkten bleiben die entsprechenden Beziehungsbefunde abhängig und offen.

### 8. Fehlend, zusätzlich und unbekannt trennen

`MISSING_ELEMENT` beziehungsweise `ADDITIONAL_ELEMENT` setzt ausreichende Interpretationsabdeckung und eine abgeschlossene Prüfung plausibler Gegenkandidaten voraus. Plausibilität benötigt mindestens eine nach den vorgesehenen `matching.evidenceRules` ausreichende Text-/Aliasevidenz oder unterscheidende Strukturevidenz. Ihre Mindestanforderungen und tatsächlich benötigten Konfigurationsparameter werden in diesem Paket getrennt vom `acceptThreshold` festgelegt und anschließend in Paket 01 und README nachgetragen: Ein Paar unterhalb der Annahmeschwelle kann weiterhin plausibel und damit ungeklärt sein. Die bloße Existenz eines berechneten Scores macht umgekehrt nicht jedes Paar zu einem plausiblen Gegenkandidaten. Unbekannte Typen, Ressourcenabbrüche oder weggefilterte Kandidaten sind kein Beweis für Abwesenheit.

Für Mengenabweichungen kann ein belastbarer Gruppenbefund möglich sein, obwohl die Identitäten offenbleiben. Im Beispiel kann ein einziges `Kontakt` unter der vereinbarten Attributdarstellung höchstens eines der zwei Referenzattribute abdecken. Daraus darf keine willkürliche Zuordnung zu `Telefon` entstehen.

## Befunde und Vergleichseinheiten

Ein Befund besitzt mindestens `id`, `code`, `status`, `referenceIds`, `studentIds`, `criterion`, `evidenceRefs`, `groupId` und `blockedBy`. Die jeweiligen Originalzellbezüge werden aus den Graphen mitgeführt. `status` unterscheidet `supported` und `unresolved`.

Beispielbefund:

```json
{
  "id": "finding-quantity-owner",
  "code": "WRONG_OWNER",
  "status": "supported",
  "referenceIds": ["r4"],
  "studentIds": ["s4"],
  "expectedOwnerReferenceId": "r3",
  "actualOwnerStudentId": "s2",
  "criterion": "attribute.owner",
  "evidenceRefs": ["mapping-quantity", "mapping-position", "mapping-order", "owner-paths"],
  "groupId": "quantity-ownership",
  "blockedBy": []
}
```

Die referenzierten Evidenzeinträge müssen im vollständigen Ergebnis oder in eindeutig benannten Eingabeartefakten vorhanden sein. Korrekt geprüfte Aspekte werden ebenfalls verzeichnet; allein eine Fehlerliste genügt später nicht für eine Rubrik.

Für die Referenzauswahl erhält jede fachliche Element- oder Beziehungsinstanz genau einmal ein Gewicht aus `comparisonConfig.selection` (Startvorschlag: Gewicht 1 je Instanz). Erzeugte technische Kanten erhalten kein eigenes Gewicht. Zugeordnete Paare bilden eine gemeinsame `comparisonUnit`, unzugeordnete Instanzen beziehungsweise offene Gruppen entsprechende eigene Einheiten.

Jede Einheit enthält die betreffenden IDs, `referenceWeight`, `studentWeight`, `deviation: { lower, upper }` und die zugrunde liegenden Befunde. Die Einheiten decken sämtliche IDs aus `coverage` genau einmal ab. Für eindeutig richtige Einheiten ist die Abweichung 0, für eindeutig fehlende/zusätzliche Einheiten 1. Bei zugeordneten, teilweise abweichenden Einheiten ergibt sie sich aus den im Auswahlprofil festgelegten Aspekten und Teilgewichten. Fehlende Evidenz erzeugt einen Bereich, keine willkürliche Teilabweichung.

Bei offenen Gruppen darf konservativ `[0,1]` verwendet werden; engere Grenzen benötigen eine nachvollziehbare Herleitung. Folgeprobleme eines bereits erfassten Grundfehlers sind über `groupId`/`blockedBy` verbunden und dürfen nicht als zusätzliche unabhängige volle Abweichungen eingerechnet werden. Das Auswahlprofil legt hierfür die Zählregel fest. Diese Vergleichsgewichte sind ausdrücklich keine Notenrubrik.

## Fehlerverhalten

Widersprüchliche Artefaktbezüge oder eine fehlende erforderliche Eingabe verhindern den Einzelvergleich. Interpretationslücken und fachliche Mehrdeutigkeit ergeben dagegen ein reguläres Teilergebnis mit den jeweils betroffenen Bereichen.

Wenn die Ressourcen nicht für eine vollständige technische Ausführung reichen, darf keine angeblich abgeschlossene Kandidatenprüfung ausgegeben werden. Initial wird der Paarlauf in diesem Fall technisch abgebrochen. Der Gesamtabschluss erhält die anderen Paarergebnisse.

## Erfüllungskriterien

- [ ] Jede bestätigte Instanzzuordnung ist partiell und One-to-One; keine erzwungenen Gegenstücke.
- [ ] Ein Element kann global erkannt werden, obwohl es beim falschen Besitzer liegt.
- [ ] Identische Labels, konkurrierende Kandidaten und Gleichstände werden nachvollziehbar behandelt.
- [ ] Zugehörigkeit, Eigenschaften und Beziehungen erzeugen lokalisierte Befunde mit Originalbezug.
- [ ] Ungeklärte Identitäten begrenzen davon abhängige Aussagen; unabhängige Befunde bleiben nutzbar.
- [ ] Die falsche Zugehörigkeit eines Attributs wird nicht zugleich als voller Fehlend-/Zusätzlich-Fehler ausgegeben.
- [ ] Alle Vergleichseinheiten sind einmalig gezählt und tragen die Grundlage ihrer Abweichung beziehungsweise ihres offenen Bereichs.
- [ ] Ein Ergebnis enthält keine Note und keinen als Wahrscheinlichkeit ausgegebenen Ähnlichkeitswert.

**Aktuelle Verifikation:** Ausschließlich statische Durchsicht der Änderungen und Schnittstellen. Keine Tests erstellen, erweitern oder ausführen; keine manuellen Modell-/Containerläufe, Builds, Benchmarks, Lint- oder Syntaxprüfungen. Die Kriterien beschreiben Sollverhalten und sind derzeit kein Auftrag zur Ausführung.

**Übergabe:** [06 – Gesamtergebnis](06-comparison-result.md) erhält einen abgeschlossenen Referenzvergleich mit zugehörigen Vergleichseinheiten.
