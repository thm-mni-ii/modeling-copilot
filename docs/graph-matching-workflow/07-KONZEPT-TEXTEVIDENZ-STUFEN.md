# 07 · Konzept: Synonymmethoden über Rollen und Evidenzstufen steuern

> **Konzept, nicht umgesetzt** · Stand 17.11.2026 · betrifft `synonym-matching` (03) und
> `one-to-one-graph-matching` (04, GM-14–18, GM-26)
> **Ziel:** Ein Gerüst, in das sich beliebige Text-/Synonymverfahren einhängen lassen, ohne
> dass jede neue Methode eine weitere gleichrangige Stimme wird. Gesteuert wird, **welche
> Entscheidung eine Methode treffen darf** und **in welcher Reihenfolge**.

## 1. Ist-Zustand und warum er nicht skaliert

```text
synonym-matching                       one-to-one-graph-matching
  Vorverarbeitung (global, für alle)     text_similarity.pair_similarity()
  → N Methoden, je ein Rohscore            supported  ⇔ ∃ Methode ≥ eigene Schwelle   (GM-15, ODER)
  → Matrix aller zulässigen Paare        semantic_refinement: Vorschlag nur, wenn das Paar
                                           ALLE Konkurrenten in ALLEN Methoden dominiert (GM-16)
                                         identity_evidence: necessary_pairs() über alle
                                           "supported"-Paare → uniquely_supported (GM-26)
```

Die Trennung „Synonymdienst liefert Evidenz, Graph-Matcher entscheidet“ ist richtig und bleibt.
Das Problem liegt in der **Kombinationsregel**: Jede Methode ist eine gleichberechtigte Stimme.

| Effekt | Folge bei mehr Methoden | Messung (Goldkorpus, 160 positiv / 48 hart negativ) |
|---|---|---|
| ODER über Schwellen (GM-15) | Fehltreffer aller Methoden addieren sich | Levenshtein allein: 12 FP · ODER über alle 4: **23 FP** |
| Dominanz über alle Methoden (GM-16) | Jede zusätzliche Methode kann ein Patt erzeugen | mehr `ambiguous_candidates`, weniger Vorschläge |
| Mittelwert | Starke Spezialisten werden verwässert | MEAN(4) ≥ 0,70: Recall 0,41 (kaum besser als Levenshtein) |
| Vorverarbeitung global | Eine Normalisierung trifft alle Methoden gleich, kann aber nicht als eigene Evidenz zählen | `casefold` nur als Schalter, nicht als „gleich nach Normalisierung“ |
| Keine Grauzone | Score knapp unter der Schwelle = „unähnlich“ | Struktur kann schwache Textevidenz nicht gezielt bestätigen |
| Kein Veto | `Version 1`/`Version 2`, `Anmeldung`/`Abmeldung` bestehen jede Ähnlichkeitsschwelle | 4/4 Methoden stimmen jeweils dafür |

Zusätzlich zeigen die Labormodelle zwei Effekte, die eine reine Scoreschwelle nicht lösen kann:

- **Abkürzungen verderben Embeddings:** `Bezeichnung`↔`Bez.` 0,48, aber `Bezeichnung`↔`Nachname` 0,96.
  Transformationen müssen *vor* bestimmten Vergleichern laufen, nicht nur global.
- **Absolute Schwellen versagen bei Konkurrenz:** `Nachname`↔`Familienname` 0,77, `Nachname`↔`Vorname` 0,98.
  Erst nachdem `Vorname` exakt verankert ist, wird `Familienname` zum eindeutig besten Rest.

## 2. Kernidee: Rollen statt Stimmen, Stufen statt Scores

> **Einordnung der Rückmeldungen vom 17.11.2026:** Sprache → als Annotation statt Gate (2.4, Gate hätte
> negativen Effekt); Abkürzungen/Sonderzeichen → generische Transformer ja, Lexikon im Code nein (2.5);
> Rollen → nach Fragen geordnet und um *Zulassung*, *Wissen*, *Entscheider* ergänzt (2.1);
> Human in the loop → übernommen als Rolle *Wissen* (4); kein Overfitting → als Leitplanken verankert (5).

### 2.1 Rollen nach der Frage, die sie beantworten

Jede Rolle hat **genau einen Ausgabetyp**. Daran lässt sich jede neue Methode eindeutig einordnen.
Die Reihenfolge der Tabelle ist zugleich der Datenfluss.

| # | Rolle | Frage | Ausgabe | Darf | Darf nicht | Ort | Beispiele |
|---|---|---|---|---|---|---|---|
| 1 | **Zulassung** | Dürfen a und b überhaupt verglichen werden? | zulässig ja/nein | Paare ausschließen | ähnlich/unähnlich sagen | Synonymdienst (besteht, SY-01–05) | Sprach-ID/-version, Vergleichsgruppe, Typ |
| 2 | **Transformer** | In welcher Form wird verglichen? | Textform je Label (+ Annotation) | „gleich nach Transformation“ → T1 | Scores liefern | Synonymdienst | casefold, Trennzeichen, Zeilenumbruch, CamelCase, Umlautschreibung |
| 3 | **Wissen** | Was ist verbindlich bekannt? | Zusicherung `equal`/`not_equal` mit Herkunft | T1-Treffer **oder** hartes Veto | Ähnlichkeit schätzen | Aufgabe/Musterlösung, gepflegt per HITL (Abschnitt 4) | Glossar der Aufgabe, abgelehnte Begriffe |
| 4 | **Comparator** | Wie ähnlich? | Score auf **einer benannten Form** | `match`/`grey`/`none` in seiner Stufe | Stufen überspringen, Vetos aufheben | Synonymdienst | Levenshtein, Embedding |
| 5 | **Guard** | Was spricht dagegen? | Vetogrund | Ähnlichkeitsverdikt blockieren | jemals `match` erzeugen | Synonymdienst | Ziffern ungleich, Präfixkontrast |
| 6 | **Entscheider** | Welche Stufe, welches Verdikt, welche Identität? | Textverdikt, Identitätsstatus | als Einziger entscheiden | neue Evidenz erfinden | nur Graph-Matcher | Stufenpolitik, `necessary_pairs`, Struktur |

Vorrang bei Widerspruch: **Wissen > Guard > Comparator.** Eine menschliche Ablehnung schlägt jeden Score;
eine menschliche Bestätigung schlägt einen heuristischen Guard. Die 1:1-Eindeutigkeit (GM-10, GM-26)
gilt auch für Wissen: Ein Glossareintrag macht ein Paar zum T1-Treffer, aber nicht automatisch eindeutig,
wenn das Label mehrfach vorkommt.

Weitere Rollen sind bewusst **nicht** vorgesehen: Sprach- oder Wortartmerkmale sind Annotationen eines
Transformers, keine eigene Entscheidungsinstanz (siehe 2.4). Die Struktur (Owner, Kinder, Verbindungen)
gehört zum Entscheider; nur sie darf eine Grauzone bestätigen oder gleich beschriftete Instanzen auflösen.

### 2.2 Eine feste, kurze Evidenzleiter

```text
T0 exakt          normalize(a) == normalize(b)                       → match
T1 kanonisch      gleiche Transformer-Form / Abkürzungsmuster         → match   (deterministisch, ohne Schwelle)
T2 Schreibweise   Comparator auf kanonischer Form, Zone [reject, accept] → match | grey | none
T3 Bedeutung      Comparator auf erweiterter Form,  Zone [reject, accept] → match | grey | none
                  Guards prüfen T2/T3-Treffer → veto
T4 relativ        nur Rest nach Ankern T0–T3: grey-Paar ist gegenseitig bestes mit Abstand → match (relativ)
──────────────────────────────────────────────────────────────────────────────────────────────
Struktur          grey/mehrdeutige Paare über Owner-/Kinder-/Verbindungsevidenz (bestehende GM-05–09)
```

Pro Paar entsteht **genau ein Textverdikt** statt N Scores:

```json
{"tier": "T3_meaning", "verdict": "match", "comparator": "multilingual", "form": "expanded",
 "score": 0.91, "zone": [0.55, 0.85], "vetoes": []}
```

Rohscores bleiben für Diagnose und Sidebar erhalten, steuern aber keine Entscheidung mehr direkt.
Eine neue Methode wird damit nicht „Stimme Nr. 5“, sondern entweder Transformer, Comparator einer
bestehenden Stufe oder Guard. Die Zahl der Stufen bleibt klein (≤ 5), auch bei vielen Methoden.

### 2.3 Wie Stufen kombiniert werden

1. **Lexikografisch statt additiv:** Das Verdikt eines Paares ist die höchste Stufe, die es akzeptiert.
   Ein T1-Treffer wird nie durch einen T3-Score relativiert.
2. **Eindeutigkeit stufenweise:** `necessary_pairs()` läuft je Stufe über die noch offenen Paare;
   Anker höherer Stufen reservieren zuerst. Genau das macht `identity_evidence` heute schon für
   `exact_label` → `text_similarity`; es wird auf eine geordnete Stufenliste verallgemeinert.
3. **Innerhalb einer Stufe** gilt pro Stufe eine deklarierte Regel: `single` (ein Comparator, Standard),
   `any`/`all`/`vote(k)` nur, wenn kalibriert nachgewiesen ist, dass sie besser als `single` ist.
4. **Grauzone ist eigener Zustand:** `grey` heißt „Text spricht nicht dagegen“. Ein grey-Paar wird
   nur über T4 (relativ im Rest) oder durch unabhängige Struktur zum Anker, nie allein über den Score.
5. **Veto ist endgültig für Textevidenz:** Ein Paar mit Veto kann nur über Struktur erkannt werden und
   erhält dann einen `label.different`-Fakt. Damit wird „Anmeldung statt Abmeldung“ zum Feedback,
   nicht zur stillen Identität.

### 2.4 Sprache: Annotation statt Gate

**Entscheidung:** keine Spracherkennung je Label als Vorbedingung für Vergleiche.

| Befund (gemessen) | Folge |
|---|---|
| Stringmethoden schlagen sprachübergreifend nur bei Kognaten an, und diese sind korrekt: `Produkt`/`Product` 0,86, `Adresse`/`Address` 0,71, `Ende`/`End` 0,75 | Ein Gate „andere Sprache → kein Textvergleich“ verliert Treffer und gewinnt nichts, denn bei echten Fremdwörtern liegen die Stringwerte ohnehin bei 0–0,3 |
| Das multilinguale Embedding trägt Deutsch/Englisch bereits: `Bestellung`/`Order` 0,90, `Gebäude`/`Building` 0,96, `Mitarbeiter`/`Employee` 0,92 | Fremdsprache wird über T3 erkannt, ohne Übersetzung oder Sprachweiche |
| Die sprachübergreifenden Fehlschläge waren Abkürzungen und Zeilenumbrüche, nicht die Sprache: `RaumNr.`/`Room number` 0,25 → 0,70 nach Ausschreiben; `Wissen\nschaftler`/`Scientist` 0,49 → 0,97 nach Zusammenführen | Vorverarbeitung (2.5) wirkt hier stärker als Spracherkennung |
| Kurze Modelllabels sind sprachlich oft unentscheidbar: `Student`, `Experiment`, `Start`, `Status`, `Name`, `Version` | Eine Erkennung je Label wäre bei genau diesen Labels unzuverlässig und würde dann falsch weichen |

Sinnvoll bleibt Sprache als **Annotation auf Modellebene** (über alle Labels einer Abgabe geschätzt, im
Inventar ist dafür bereits `textLanguage` vorgesehen, heute `null`):
- als Weiche für **sprachspezifische Transformer** (Umlautschreibung, Kompositumzerlegung nur für Deutsch);
- als **Feedbackfakt** („Labels überwiegend Englisch, Musterlösung Deutsch“) und Hinweis für den HITL-Reviewer;
- nicht als Ausschluss, nicht als Schwellenveränderung.

Übersetzung als Transformer bleibt eine Idee für den Fall, dass F1 mit dem Embedding nicht reicht (heute 6/9).
Sie bringt ein weiteres Modell und eine weitere Fehlerquelle; ohne Messgewinn wird sie nicht aufgenommen.

### 2.5 Vorverarbeitung: Wie weit?

**Regel:** Eine Transformation wird aufgenommen, wenn sie *generisch* ist (nicht aus Testdaten abgeleitet),
*keine Bedeutung trägt*, die ein Guard braucht, und auf den harten Negativen des Goldkorpus keinen neuen
Fehltreffer erzeugt. Transformer erzeugen **zusätzliche Formen**; Original und `normalize`-Form bleiben
unverändert erhalten und für exakte Anker maßgeblich.

| Transformation | Einordnung | Begründung |
|---|---|---|
| NFC, Whitespace | bleibt (heute schon) | bedeutungsneutral |
| casefold | **aufnehmen** (Form `canonical`) | A1 8/8; keine neuen Fehltreffer |
| Trennzeichen, Bindestrich, Unterstrich, CamelCase-Grenzen entfernen | **aufnehmen** (`canonical`) | A2/A3 8/8 |
| weicher Zeilenumbruch im Wort (`Wissen\nschaftler`) zusammenführen | **aufnehmen** (`expanded`) | Editorartefakt, stärkster Einzeleffekt beim Embedding |
| Umlautschreibung ä→ae, ß→ss | **aufnehmen**, nur bei deutscher Modellannotation | F2; im Englischen bedeutungslos |
| Punktabkürzung als Muster (gleicher Anfang + geordnete Teilfolge: `ProjektNr.`~`Projektnummer`) | **aufnehmen** als T1-Regel, nicht als Umschreibung | generisch, A7 teilweise; der Punkt muss dafür in `canonical` erhalten bleiben |
| Abkürzungslexikon im Code (`Nr.`→`Nummer`) | **verwerfen** → Glossar/HITL | gemessen: Goldkorpus unverändert, eindeutige Laborzuordnungen unverändert; es half nur bei Labels, aus denen es abgeleitet war (Overfitting) |
| Ziffern/Indizes entfernen | **verwerfen** | zerstört den Ziffern-Guard (`Version 1`/`Version 2`) |
| Sonderzeichen mit Bedeutung (`£`, `#`, `+`, `%`) entfernen | **nur in `canonical`**, nie in der Exaktform | `C#`/`C` würde sonst T1-gleich; bei Bedarf als Guard „Symbol ungleich“ |
| Stemming/Lemmatisierung | **Idee, nicht aufnehmen** | B1 erreicht T2 bereits 6/9; sprachabhängig, eigene Fehlerklasse |

## 3. Einbau in den bestehenden Ablauf

| Ort | Änderung | Bleibt |
|---|---|---|
| `synonym-matching/methods/registry.py` | `MethodDefinition` erhält `role` (`transformer`/`comparator`/`guard`) und bei Comparatorn `form` (welche Transformer-Form). Neue Methoden werden nur dort registriert. | Rohscores, Hashes, Vollständigkeit der Matrix |
| `synonym-matching/service.py` | Je Label die Transformer-Formen einmal berechnen (`processedTexts` je Form); Comparators auf ihrer Form; Guards je Paar als `vetoes` in den Kandidaten. **Keine** Stufenentscheidung. | „keine Identitätsentscheidung im Synonymdienst“ (SY-11) |
| `semantic-candidates` | `scores` bleiben; neu `forms` (pro Label) und `vetoes` (pro Paar). Schema-Version erhöhen. | Paarzulässigkeit SY-01–05 |
| `graph-matching/text_similarity.py` | `pair_similarity()` wird zu `pair_text_verdict()`: liest die Stufenpolitik, ordnet jedes Paar einer Stufe und einem Verdikt zu. Einziger Ort für Schwellen. | Validierung gegen `scoreRange` (GM-14) |
| `graph-matching/identity_evidence.py` | Die Schleife `exact_anchors`/`similarity_anchors` wird zur Schleife über die geordneten Stufen; Kriterium `text_similarity` trägt `tier`. | GM-13 kein Zirkelschluss, GM-26 Statusbegriffe |
| `graph-matching/semantic_refinement.py` | Dominanz über alle Methoden entfällt; Konkurrenz wird über Stufenrang und Score der **einen** Stufe entschieden. grey-Paare nur mit `ownerAnchorRelation: consistent` oder über T4. | Kapazitätsprüfung GM-18 |
| `comparisonConfig` | neu `textEvidence.tiers` (siehe unten); `graphMatching.minimumSimilarity` wird intern auf eine T2-Stufe abgebildet. | Workflowparameter `levenshtein_threshold` funktioniert unverändert |
| Sidebar (`semanticComparison.ts`) | zeigt pro Kandidat Stufe + Verdikt + Veto; Rohscores aufklappbar | bestehende Kandidatenansicht |

Beispielkonfiguration (Werte aus Abschnitt 6):

```json
{
  "semantics": {
    "transformers": ["canonical", "expanded"],
    "methods": ["levenshtein", "multilingual"],
    "guards": ["digit_mismatch", "prefix_contrast"]
  },
  "textEvidence": {
    "tiers": [
      {"name": "T1_canonical", "kind": "equal_form", "form": "canonical"},
      {"name": "T2_spelling", "comparator": "levenshtein", "form": "canonical", "accept": 0.85, "reject": 0.60, "guards": true},
      {"name": "T3_meaning", "comparator": "multilingual", "form": "expanded", "accept": 0.85, "reject": 0.55, "guards": true},
      {"name": "T4_relative", "kind": "residual_best", "comparator": "multilingual", "margin": 0.05}
    ]
  }
}
```

**Optional später (Zielidee aus 03):** Comparators teurer Stufen nur für Paare berechnen, deren beide
Seiten nach T0/T1 noch offen sind. Nicht berechnete Paare werden `not_scored`, nicht „unähnlich“;
die Konkurrenzmenge bleibt aus der Matrix rekonstruierbar. Erst angehen, wenn Laufzeit ein Problem ist.

## 4. Human in the loop als Rolle „Wissen“

Der Reviewer ist keine nachträgliche Korrektur der Ausgabe, sondern eine **Evidenzquelle mit Vorrang**.
Seine Entscheidungen fließen beim nächsten Lauf als Zusicherungen ein und durchlaufen denselben Entscheider.

**Was der Reviewer sieht** (Admin-Auswertungsansicht, 06, Tab „Befunde“, nur Service-Perspektive):

| Warteschlange | Herkunft |
|---|---|
| Unsichere Synonyme | Paare mit Verdikt `grey`, die weder T4 noch Struktur aufgelöst hat |
| Struktur sagt ja, Text sagt nein | strukturell erkannte Paare mit Veto oder `none` |
| Offene Referenzbegriffe | Referenzobjekte ohne Gegenstück, mit den drei besten zulässigen Kandidaten |

**Was er tun kann:**

| Aktion | Wirkung | Geltungsbereich (explizit wählen) |
|---|---|---|
| Bestätigen | `equal`-Zusicherung → T1 | „nur diese Abgabe“ **oder** „für die Aufgabe übernehmen“ |
| Ablehnen | `not_equal`-Zusicherung → hartes Veto, `label.different`-Fakt | ebenso |
| Begriff nachtragen | Referenzbegriff → zusätzliche akzeptierte Bezeichnungen | Aufgabe (Glossar der Musterlösung) |

**Leitplanken:**
- **Speicherort:** Glossar an der Aufgabe/Musterlösungsversion, nicht global. Fachsynonyme sind aufgabenabhängig (C2):
  „Auftrag“ = „Bestellung“ gilt nicht in jeder Domäne.
- **Reproduzierbarkeit:** Zusicherungen werden Teil des eingefrorenen Snapshots (`evaluation-input`, `inputHash`).
  Eine Glossaränderung verändert alte Läufe nicht still; Neubewertung ist eine bewusste Aktion.
- **Herkunft:** wer, wann, Geltungsbereich, auslösendes Paar. Die Sidebar zeigt „vom Reviewer bestätigt“ getrennt
  von „automatisch erkannt“, damit die Erkennungsquote nicht verwischt.
- **Nur Labelgleichwertigkeit:** Der Reviewer sagt „Begriff X bedeutet Y“, nicht „Element 17 ist Element 4“.
  Die Instanzwahl bleibt beim Matcher; so bleibt eine Zusicherung auf andere Abgaben übertragbar.
- **Nicht zum Schwellentuning:** Reviewerentscheidungen werden als zusätzlicher Prüfkorpus gesammelt,
  aber Schwellen nicht je Aufgabe nachgezogen (siehe 5).

## 5. Kalibrierung und Grenzen gegen Overfitting

**Grundsatz:** Nicht erkannt ist ein gültiges Ergebnis. Ein Begriff, der sich nur mit aufgabenspezifischen
Sonderregeln auf die Musterlösung abbilden lässt, ist fachlich zu weit weg und wird Feedback oder HITL-Fall,
nicht Ziel weiterer Regeln. Konkrete Leitplanken:

- **Feste Struktur:** höchstens fünf Stufen; eine neue Methode ersetzt oder ergänzt eine Stufe, sie bekommt keine eigene.
- **Präzision vor Recall:** Schwellen aus einem Präzisionsziel (≥ 0,95), nie aus Recall je Kategorie.
- **Keine Regeln aus Prüfdaten:** Lexika, Präfixlisten und Ausnahmen, die aus den Labormodellen oder dem
  Goldkorpus stammen, gehören ins Glossar der jeweiligen Aufgabe, nicht in den Code. Das Prototyp-Lexikon
  wurde aus diesem Grund verworfen (2.5).
- **Getrennte Prüfmengen:** Goldkorpus für Schwellen, Labormodelle und HITL-Fälle nur zur Kontrolle von
  „0 falsche eindeutige Zuordnungen“.
- **Bewusst nicht verfolgt:** Kontextsynonyme (C2, E1, E2), Ober-/Unterbegriffe (C3, `partial`),
  Übersetzungsstapel, Stemming. Hier ist die Abweichung von der Musterlösung didaktisch relevant und
  gehört ins Feedback.

Jede Stufe hat genau zwei Zahlen und eine Begründung aus dem Goldkorpus
(`synonym-matching/calibration/label-variants.json`):

- `accept`: kleinste Schwelle mit Präzision ≥ 0,95 auf `equivalent`/`not_equivalent`.
- `reject`: darunter liegen ≤ 5 % der Positiven dieser Stufe.
- Eine Methode kommt nur in die Leiter, wenn sie gegenüber der bestehenden Stufe Recall bei gleicher
  Präzision hinzufügt (Ablation). Beispiel aus dem Sweep: Jaro-Winkler (0,95: P 0,95 / R 0,23) und
  Zeichen-Trigramme (0,85: P 1,00 / R 0,03) liegen nicht über Levenshtein auf kanonischer Form
  (0,85: P 0,94 / R 0,28). Sie brauchen keine eigene Stufe.
- Die Labormodelle (`v12_laboratory_management/synonym_*.json`) dienen als Gegenprobe im
  Modellkontext: Kennzahl ist „falsche eindeutige Zuordnungen = 0“, erst danach Recall.

## 6. Erprobung mit den Testdaten

Die Methoden des Dienstes wurden unverändert im Image `synonym-matching:v2` ausgeführt. Die Strategien
sind als Prototyp nachgebaut (`.local/tmp/synonym-concept/evaluate.py`), nicht im Dienst implementiert.

**Goldkorpus (paarweise, ohne Konkurrenz):**

| Strategie | Präzision | Recall | FP (von 48) | grey (pos/neg) |
|---|---|---|---|---|
| S0 nur exakt | 1,00 | 0,01 | 0 | – |
| S1 Levenshtein ≥ 0,75 (heutige Konfiguration) | 0,83 | 0,38 | 12 | – |
| S2 ODER über 4 Methoden (GM-15 mit allen Methoden) | 0,83 | 0,70 | 23 | – |
| S3 Mittelwert 4 Methoden ≥ 0,70 | 0,86 | 0,41 | 11 | – |
| K1 Leiter T0–T3, ohne Guards | 0,85 | 0,68 | 19 | 39/22 |
| K3 Leiter T0–T3 mit Guards | 0,89 | 0,68 | 13 | 39/22 |
| **K4 Leiter + Transformer vor Embedding, Schwellen 0,85** | **0,94** | **0,62** | **6** | 49/29 |

Abdeckung von K4 je Kategorie (Recall): A1–A3 8/8 (T1), F2 8/9, D2 8/8, A8 3/4, A7 4/10, C1 4/10, F1 6/9,
C2/E2 0 (Kontext → Struktur). Der Ziffern-Guard greift nur, wenn **beide** Seiten Ziffern tragen und
diese abweichen (`Version 1`/`Version 2`); ein einseitiger Index (`Kunde`/`Kunde2`) ist Instanznummerierung.
Verbleibende FP: Meronymie/Kompositum (`Bestellung`/`Bestellposition`, `Warenkorb`/`Warenkorbeintrag`),
Antonyme ohne Präfix (`Import`/`Export`, `Wareneingang`/`Warenausgang`), verwandte Begriffe (`Arzt`/`Patient`),
Kohyponyme (`Vorname`/`Nachname`). Die Guards „Kompositumkopf“ und „Antonymlexikon“ wären die passenden Erweiterungen;
Kohyponyme löst im Modell die Konkurrenz (beide Labels existieren, T0 verankert eines zuerst).

**Labormodelle (Musterlösung gegen 5 Varianten, Konkurrenz innerhalb des Elementtyps, nur Text, ohne Struktur):**

| Modell (geänderte Labels) | S1 heute: eindeutig korrekt | K4: eindeutig korrekt | falsch eindeutig (alle Strategien) |
|---|---|---|---|
| Schreibweise (14) | 4 | 5 | 0 |
| Tippfehler/Abkürzungen (18) | 3 | 3 (+15 textlich korrekt, aber mehrdeutig) | 0 |
| Fachbegriffe (15) | 0 | 3 | 0 |
| Sprachmix (19) | 0 | 3 | 0 |
| Abgrenzung (6, überwiegend Negative) | 0 | 1 (`Ende`→`Schluss`, korrekt) | 0 |

Die große Restmenge „textlich korrekt, aber mehrdeutig“ entsteht durch wiederholte Attributlabels
(`GebäudeNr.` fünfmal, `ProjektNr.` viermal). Das ist **keine Textaufgabe**: Die Leiter liefert die
richtige Äquivalenzklasse, die Instanz wählt die vorhandene Owner-/Kinderlogik (GM-05, GM-09).
Genau diese Arbeitsteilung macht das Konzept explizit.

**Ablation Abkürzungslexikon** (`Nr.`, `Bez.`, `Anz.`, aus den Labormodellen abgeleitet): Goldkorpus und
eindeutige Laborzuordnungen identisch mit und ohne Lexikon; nur „textlich korrekt, aber mehrdeutig“ sinkt
ohne Lexikon (Fachbegriffe 6 → 2, Sprachmix 12 → 4). Das Lexikon wird deshalb nicht Teil des Codes;
solche Einträge kommen über das Aufgabenglossar (4).

## 7. Vorschläge, welche Verfahren wohin passen

| Stufe/Rolle | Empfehlung | Deckt ab |
|---|---|---|
| Transformer `canonical` | NFC, casefold, ä→ae/ß→ss, Trennzeichen/Bindestrich/Zeilenumbruch entfernen | A1–A3, F2, Teile A6 |
| T1 Abkürzungsmuster | Punktabkürzung = gleicher Anfang + geordnete Teilfolge (`ProjektNr.`~`Projektnummer`, `Bez.`~`Bezeichnung`) | A7 |
| Transformer `expanded` | Zeilenumbruch im Wort zusammenführen, CamelCase trennen; Abkürzungen nur über das Aufgabenglossar | Vorbedingung für T3 |
| Wissen | Aufgabenglossar aus HITL (bestätigt/abgelehnt/nachgetragen) | aufgabenspezifische Synonyme, C2 |
| Annotation Sprache | Schätzung auf Modellebene in `textLanguage`; Weiche für deutsche Transformer, Feedbackfakt | Sprachmix als Hinweis, nicht als Gate |
| T2 Comparator | Levenshtein auf `canonical` | A4, B1, D1 |
| T3 Comparator | multilinguales Embedding auf `expanded`; Übersetzung (`louis/translation.py`) nur als alternativer Transformer, falls F1 nicht reicht | C1, D2, D4, D5, F1 |
| Guards | Ziffern, Präfixkontrast; Vorschlag: Kompositumkopf, Antonymlexikon | A8, C4, C5 |
| Struktur (bestehend) | grey-Paare, wiederholte Labels, E1/E2/C2 | Kontextkategorien |

## 8. Umsetzung in kleinen Schritten

1. **Verdiktadapter** in `text_similarity.py` mit Stufenliste; `minimumSimilarity` als Ein-Stufen-Fall.
   Kein Schemawechsel, sofort testbar mit heutigen Scores.
2. **Stufenschleife** in `identity_evidence.py` und Stufenrang statt Methoden-Dominanz in `semantic_refinement.py`.
3. **Transformer-Formen und Guards** im Synonymdienst (`forms`, `vetoes`, neue Schemaversion).
4. **Kalibrierskript** von Levenshtein auf Stufen erweitern (Präzisionsziel, Ablation je Methode).
5. **T4 relativ und grey + Struktur** aktivieren, erst nach Prüfung „0 falsche eindeutige Zuordnungen“ an den Labormodellen.
6. Sidebar: Stufe/Verdikt/Veto statt Scoreliste.
7. **HITL:** Glossar an der Aufgabe (API + Snapshot-Aufnahme), Warteschlange und Aktionen in der Befundliste.
   Kann parallel zu 3–5 entstehen, weil es nur die Rolle „Wissen“ füllt.

**Umsetzungsstand 17.11.2026 (Prototyp):** Schritte 1–2 umgesetzt, Schritt 3 nur für Transformer-Formen.
- Synonymdienst `1.2.0` (Image `v3`): Vorverarbeitung `casefold`, `split_identifiers`, `expand_abbreviations`;
  Vergleichsvarianten `levenshtein_canonical` (Form `canonical`) und `multilingual_expanded` (Form `expanded`,
  teilt das Modell mit `multilingual`). Standardmethoden unverändert.
- Graph-Matcher `2.3.0` (Image `v7`): `graphMatching.textEvidence.tiers` (geordnete Stufen aus je
  `name` + `minimumSimilarity`); `minimumSimilarity` ist der Einzelstufen-Fall. Stufenrang in der Konkurrenz,
  stufenweise Reservierung in der Identitätsbewertung, Kriterium `text_similarity` trägt `tier`.
- Aktivierung: Admin-Dialog „Evidenzstufen (Prototyp)“ → API `textEvidence: "tiers"` → Workflowparameter
  `text_evidence` → `workflow-data` (`v3`) friert die Voreinstellung ein (kanonisch = 1,0, Schreibvariante
  `levenshtein_canonical` ≥ 0,85, Bedeutung `multilingual_expanded` ≥ 0,85).
- Messung mit dem Dienstcode (`.local/tmp/synonym-concept/check_service.py`): Goldkorpus P 0,89 / R 0,59 /
  12 FP (heute Levenshtein ≥ 0,75: 0,83 / 0,38 / 12); Labormodelle ohne falsche eindeutige Zuordnung.
  Die verbleibenden FP (Ziffern, Gegensätze, Teil-Ganzes) sind Guard-Fälle; Guards, Grauzone, T4 und HITL
  sind noch offen.

**Nachtrag 17.11.2026 · Substruktur statt Platzierung (Graph-Matcher `2.4.0`, Image `v8`):** Die
Identitätslogik nutzt den Besitzer nur noch, wenn der Parser ihn über eine deklarierte Substruktur
(`component`) erreicht; bloße Platzierung (`content` in einem anderen Fachobjekt, z. B. Lane) bleibt ein
Lagebefund. Grundlage für die Vorschläge zu Attributen semantisch erkannter Objekte, diskriminierenden
Kindern und vertauschten Beschriftungen in sprachübergreifender Form; für SERM unverändert (v15-Lauf
identisch). UML-Klassenmitglieder gelten erst als Substruktur, wenn die Sprachdefinition sie als Kinder
deklariert.

**Nachtrag 17.11.2026 · Vorschläge 1–5 (Graph-Matcher `2.5.0`/`v9`, Synonymdienst `1.3.0`/`v4`):**
kanonische Form mit Umlautumschrift und ohne Trennzeichen, Damerau-Levenshtein für die Schreibweise
(Goldkorpus R 0,588 → 0,619, Fehltreffer unverändert 12); GM-04a vertauschte Beschriftungen als Prüffall,
GM-07a eindeutige Konfliktkinder blockieren (statt Seltenheitsregel, die v14 verschlechtert hätte), GM-18a
zweiter Durchlauf für Substruktur-Kinder semantischer Besitzer, GM-18b Graubereich ab `confirmationFloor`
0,70 mit Nachbarbestätigung. „Bedeutung allein nie eindeutig“ (Variante B) ist nicht umgesetzt und nicht gemessen:
Nach Analyse der Nachbarschaft (Forscher stützt Arbeitseinsatz und Projektbeteiligung gleich) würde keine
allgemeine Bestätigungsregel `arbeitet mit an` auflösen, ohne zugleich Recall zu kosten. Ergebnisse: `08-TESTMODELLE-V15.md`.

**Nachtrag 23.11.2026 · Teilerkennung ohne Identität (Graph-Matcher `2.11.1`, Image `v22`):** Im Glossar
standen korrekte Begriffe als nicht akzeptiert, wenn gleichnamige Elemente oder ein unerkannter Besitzer die
Eindeutigkeit verhinderten. Solche Begriffe erscheinen jetzt als `partial` und zählen weiterhin nicht
(GM-40 in `04-GRAPH-MATCHING.md`). Damit bleibt das Stufenkonzept erhalten: Stufen gelten lexikografisch,
innerhalb einer Stufe entscheidet die Dominanz über alle gemeinsamen Methoden, und Vetos gelten unverändert.
Vom Menschen akzeptierte Begriffe bleiben als `identified_glossary` von automatischer Textevidenz getrennt.

## 9. Grenzen dieser Erprobung

- Schwellen sind auf demselben Goldkorpus gewählt, auf dem gemessen wurde; die Werte sind optimistisch.
  Die Labormodelle sind die einzige unabhängige Probe und klein (5 × 48 Elemente).
- Die Labormessung nutzt nur Text und Elementtyp; Owner-/Kinderevidenz des Graph-Matchers fehlt.
  Im echten Lauf werden mehr der mehrdeutigen Paare aufgelöst.
- Guard-Präfixliste und Abkürzungslexikon sind Prototypen, keine geprüften Ressourcen.
- Verbindungstexte (`connectionTextMatrix`) wurden nicht gemessen; das Konzept gilt für sie unverändert.

## 10. Methodenbestand, Lücken und Zuständigkeit

Louis' Arbeit (`synonym-matching-louis`) ist die **Methodenbibliothek** des Projekts. Der Zieldienst
`synonym-matching` übernimmt daraus, was eine Stufe braucht, wie bisher mit Herkunftsangabe (Git-Blob
im README). Damit nichts doppelt entsteht, gilt eine einfache Arbeitsteilung:

| Wer | Liefert | Schnittstelle |
|---|---|---|
| **Louis** | Methoden: Transformer, Comparators, Guards, Sprachannotation, jeweils mit Messung | Transformer `(text, language) → text`; Comparator `(left, right) → Matrix` mit `scoreRange`; Guard `(left, right) → Vetogrund je Paar oder leer` |
| **Integration (wir)** | Registry mit Rolle, Stufenpolitik, Grauzone, Stufenschleife im Graph-Matcher, Glossar, HITL, Sidebar | `semantic-candidates`, `comparisonConfig.textEvidence`, Snapshot |
| **Gemeinsam** | ein Goldkorpus (`synonym-matching/calibration/label-variants.json`) als gemeinsamer Maßstab | jede neue Methode wird zusätzlich dort gemessen, Kriterium: kein neuer Fehltreffer bei harten Negativen |

Die Prototyp-Funktionen aus `.local/tmp/synonym-concept/evaluate.py` (kanonische Form, Abkürzungsmuster,
Ziffern-/Präfix-Guard, relativer Schritt) sind **Spezifikation, kein Zielcode**: Die Methoden darunter
entstehen einmal bei Louis, der relative Schritt einmal im Graph-Matcher.

### 10.1 Gesamtbestand je Rolle

✅ vorhanden und übernehmbar · 🟡 vorhanden, braucht Anpassung · ❌ fehlt

| Rolle / Stufe | Methode | Stand | Quelle |
|---|---|---|---|
| Zulassung | Sprach-ID/-version, Vergleichsgruppe, Typ | ✅ | Zieldienst (SY-01–05) |
| Sprachannotation | Sprache je Modell schätzen (de/en) | ❌ | – |
| Transformer `canonical` | NFC/Whitespace | ✅ | beide |
| | Kleinschreibung, CamelCase/Unterstrich trennen | ✅ | Louis `lowercase`, `split_identifiers` |
| | Umlautschreibung (ä→ae, ß→ss), weicher Zeilenumbruch im Wort, Trennzeichen entfernen | ❌ | Prototyp |
| T1 Gleichheit | Abkürzungsmuster allgemein (`Bez.`~`Bezeichnung`, `ProjektNr.`~`Projektnummer`) | 🟡 | Louis `expand_abbreviations` kann nur `Nr.`; Prototyp hat das allgemeine Muster |
| Transformer (für Guards) | Kompositum zerlegen, Kopfwort bestimmen | ✅ | Louis `split_compounds`, `split_label_parts` (OpenThesaurus) |
| Transformer (optional) | Übersetzung DE→EN | ✅ | Louis `translate` |
| T2 Schreibweise | Levenshtein | ✅ | Zieldienst (aus Louis übernommen) |
| | Damerau-Levenshtein, Token-Sortierung | ✅ | Louis, als Ablationskandidaten |
| T3 Bedeutung | multilinguales Embedding | ✅ | Zieldienst (aus Louis übernommen) |
| | übersetztes Embedding, Lexika (OpenThesaurus, OdeNet, WordNet, `wn_translation`) | ✅ | Louis |
| Guard | Kennungs-/Objektkonflikt (`GebäudeNr.`~`ProjektNr.`) | 🟡 | Louis `label_part_compatibility`: wirkt auf den Labordaten (FP 100 → 12), auf dem Goldkorpus 0 Treffer, weil die Objektliste auf die Labordomäne zugeschnitten ist → verallgemeinern |
| | Antonym, Ober-/Unterbegriff | 🟡 | Louis WordNet/OdeNet `relation_features`; als Veto verpacken, OdeNet ins Image |
| | Lexikonabdeckung („nicht abgedeckt“ ≠ „unähnlich“) | ✅ | Louis `pair_known`, `crosslingual_coverage` |
| | Ziffern ungleich | ❌ | Prototyp |
| | Negation/Präfixkontrast (`nicht`, un-/in-, an/ab, ein/aus) | ❌ | Prototyp (nur Präfixe) |
| | Kompositum mit anderem Kopf (`Bestellung`/`Bestellposition`, `Geräte`/`Geräteraum`) | ❌ | Grundlage vorhanden (`split_compounds`) |
| Wissen | Aufgabenglossar, HITL | ❌ | Integration |
| Entscheider | Stufenpolitik, Grauzone, Stufenschleife | ❌ | Integration |
| | relativer Schritt (gegenseitig bester Rest) | 🟡 | Louis `mutual_best` als Vorlage; Umsetzung im Graph-Matcher über offene Paare |
| Querschnitt | Label-Cache für Embeddings/Übersetzungen | ✅ | Louis `cache.py` |
| | Kalibrierung je Stufe | 🟡 | Zieldienst `calibrate_threshold.py` (nur Levenshtein), Louis `research/compare.py` |

**Comparators fehlen keine.** Was fehlt, sind Guards, ein Teil der kanonischen Form, die Sprachannotation
und die Integrationsschicht.

### 10.2 Reicht der Bestand für einen ersten Prototyp?

**Ja.** Der Prototyp aus Abschnitt 6 (K4: Präzision 0,94, Recall 0,62, 6 FP) nutzt nur Levenshtein,
das multilinguale Embedding und kleine Transformer/Guards. Ein lauffähiger erster Durchstich braucht:

| Baustein | Herkunft | Aufwand |
|---|---|---|
| T0 exakt, T2 Levenshtein, T3 Embedding | vorhanden | – |
| `canonical` + Abkürzungsmuster (T1) | Louis `lowercase`/`split_identifiers` + drei kleine Ergänzungen | klein |
| Ziffern- und Präfix-Guard | neu, klein | klein |
| Stufenadapter, Stufenschleife, Grauzone | Integration (Abschnitt 8, Schritte 1–2) | mittel |
| Glossar + HITL-Warteschlange | Integration (Abschnitt 4) | mittel bis groß |

Lexikon-Guards (Antonym, Ober-/Unterbegriff) und der verallgemeinerte Kennungs-Guard kommen in Runde 2
dazu; sie verbessern Präzision, sind aber für den Durchstich nicht nötig.

### 10.3 Methodenaufträge (Vorschlag für Louis)

In der Reihenfolge ihres erwarteten Nutzens; jede mit Messung auf Goldkorpus **und** Labordaten:

1. **Kennungs-/Kopfwort-Guard verallgemeinern:** `label_part_compatibility` ohne feste Objektliste.
   Kopfwort per `split_compounds` bestimmen; Veto, wenn beide eine Kennung tragen und die Kopfwörter auf
   T0–T3 nicht gleich sind. Gleiches Werkzeug für den **Kompositum-Guard** (gleicher Anfang, anderer Kopf).
2. **Negations-/Präfixkontrast-Guard** für de/en (`nicht`, `kein`, un-/in-/dis-, an/ab, ein/aus, auf/zu).
3. **Lexikon-Guard:** WordNet/OdeNet `antonym` und `reference_hypernym`/`reference_hyponym` als Vetogrund mit
   Abdeckungsstatus; OdeNet im Docker-Build bereitstellen.
4. **Transformer-Ergänzungen:** Umlautschreibung, weicher Zeilenumbruch, allgemeines Punktabkürzungsmuster
   (Spezifikation: `abbreviation_of()` im Prototyp) als Schritte in `STEPS`.
5. **Sprachannotation je Modell** (de/en/gemischt), z. B. über Lexikonabdeckung aller Labels; ersetzt
   die heutige Pflichtangabe `de`/`en` je Label in Louis' sprachabhängigen Schritten.

Optional, nur bei Bedarf nach dem Durchstich: Token-Sortierung (D2) und Damerau-Levenshtein (A4) als
Ablation gegen Levenshtein; Übersetzungspfad gegen das multilinguale Embedding bei F1.

### 10.4 Integrationsaufgaben (unsere Seite)

1. Registry: Rolle je Methode, Guard-Ausgabe `vetoes` in `semantic-candidates`.
2. Stufenadapter in `text_similarity.py`, Stufenschleife in `identity_evidence.py`, Stufenrang in
   `semantic_refinement.py` (Abschnitt 8, Schritte 1–2).
3. Glossar an der Aufgabe inklusive Snapshot-Aufnahme; HITL-Warteschlange und Aktionen in der Befundliste.
4. Kalibrierskript auf Stufen erweitern, sodass Louis' neue Methoden mit demselben Maßstab gemessen werden.
