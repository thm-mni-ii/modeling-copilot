# 03 · Synonym Matching

> **Ist-Dokumentation** · Stand: `dagu(6).zip`, 16.11.2026 · Service `synonym-matching` · `semantic-candidates/v1`  
> **Aufgabe:** Für **ein** Paar aus Abgabe und Musterlösung alle **zulässigen Textkandidaten** bilden und unabhängige Ähnlichkeitswerte liefern. **Keine Identitätsbestätigung, keine Graphüberlagerung, keine globale 1:1-Entscheidung.**

## Ablauf auf einen Blick

```text
Inventar Abgabe + Inventar Referenz + comparisonConfig
  → Hash-, Quellen- und Sprachkonsistenz prüfen
  → zulässige Paarbereiche (Sprache/Version/Gruppe/Typ) bilden
  → matchText je Methode vorbereiten
  → vier unabhängige Vergleichsverfahren berechnen
  → vollständige Kandidatenmatrix + Textstatus veröffentlichen
```

**Aktuell wichtig:** Die Text-„Vorprüfung“ ersetzt **noch kein Scoring-Trimming**. Der Dienst bildet derzeit die komplette zulässige Matrix, auch wenn einige Paare bereits exakt gleiche Texte besitzen.

## Eingabe → Ausgabe

| Eingang | Inhalt |
|---|---|
| `labels/submission.json` | Inventar der Abgabe |
| `labels/<referenceKey>.json` | Inventar genau einer Musterlösung |
| `comparisonConfig.semantics` | Optional aktivierte Methoden und Vorverarbeitung |

**Ausgabe:** `candidates/<referenceKey>.json` plus `stdout` (`candidates-result.json`), `workflow-result/v1 → result.schema = semantic-candidates/v1`. Enthält `synonymMatrix`, `connectionTextMatrix`, `unscoredElements`, methodenspezifische Metadaten, `candidatePairCount`, `scoredPairCount`, `unavailablePairCount`, Herkunft und `candidateHash`.

## 1. Welche Paare sind überhaupt zulässig?

| Regel | Ergebnis |
|---|---|
| **SY-01 · Sprache** | Nur **identische `languageId` und `versionId`**. Die natürliche `textLanguage` steuert nicht die Modelltypkompatibilität. |
| **SY-02 · Explizite Gruppen** | Sind beide Typen explizit gruppiert, ist **genau dieselbe Gruppen-ID** nötig; konkrete Typen dürfen innerhalb der Gruppe verschieden sein. |
| **SY-03 · Ungruppierte Typen** | Haben beide **keine** Vergleichsgruppe, müssen die konkreten Typen identisch sein. |
| **SY-04 · Kein Mischen** | Eine Instanz mit expliziter Gruppe und eine ohne Gruppe sind **nicht kompatibel**, selbst bei gleichem Typnamen. |
| **SY-05 · Instanzen** | Wiederholte Beschriftungen werden **nicht zusammengeführt**: Jede zulässige Referenz-/Abgabe-ID bleibt eigenes Kandidatenpaar. Eine Referenz ohne kompatible Abgabe bekommt `matches: []`. |

Die Kandidatengruppen werden **vor** der teuren Scoreberechnung aufgebaut. Ein leerer oder nicht auswertbarer Text macht ein typkompatibles Paar **nicht unzulässig**.

## 2. Wie wird der Text behandelt?

| Regel | Umsetzung |
|---|---|
| **SY-06 · Textbasis** | Nur `matchText` aus dem Inventar, nicht freie Graph-/Layoutinformationen. Originaltext und Modellsprache bleiben separat erhalten. |
| **SY-07 · Standardvorverarbeitung** | NFC-Normalisierung und Whitespace-Zusammenfassung (`normalize`). Konfigurierbare, registrierte Schritte sind erlaubt. Kein implizites Lowercasing, Übersetzen oder Sprachraten. |
| **SY-08 · Fehlender Text** | `labelStatus: missing` oder `unsupported` → Kandidat bleibt mit `scoreStatus: unavailable`, Grund und `scores: null` bestehen; die Instanz erscheint auch in `unscoredElements`. |
| **SY-09 · Wiederverwendung** | Gleiche vorbereitete Texte werden je Methode innerhalb eines Aufrufs einmal bewertet; IDs bleiben als getrennte Instanzen erhalten. Embedding-Modell/Textvektoren werden innerhalb des Aufrufs wiederverwendet. |

## 3. Welche Methoden liefern Evidenz?

| Methode | Bereich | Was bedeutet der Wert? |
|---|---|---|
| Levenshtein | `[0, 1]` | Zeichenbasierte Ähnlichkeit |
| Jaro-Winkler | `[0, 1]` | Zeichenbasierte Ähnlichkeit mit Gewicht auf Übereinstimmungen am Wortanfang |
| Zeichen-Trigramme | `[0, 1]` | Überlappung von Zeichen-Dreierfolgen |
| Multilinguales Embedding | `[-1, 1]` | Cosinus-Ähnlichkeit im Textvektorraum |

**SY-10 · Konfiguration:** Ohne `semantics.methods` werden **alle vier** Methoden verwendet. Nur registrierte, eindeutige Methoden/Preprocessing-Schritte sind gültig. Unbekannte/doppelte Werte sind Konfigurationsfehler.

**SY-11 · Unabhängige Scores:** Keine Gewichtung, kein Kombinationsscore, keine Kalibrierung auf „Wahrscheinlichkeit korrekt“, keine Top-k-Filterung und **keine Identitäts-/Thresholdentscheidung in diesem Dienst**. Scores behalten ihre methodenspezifischen Bereiche.

**SY-12 · Embedding-Ressource:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, festgelegte Revision, offline/CPU. Ohne nutzbare Textpaare wird das Modell nicht geladen. Ressourcen-/Methodenfehler führen zum Abbruch, nicht zum stillen Ersatz durch ein anderes Verfahren.

## 4. Verbindungstexte getrennt behandeln

**SY-13 · Textslot-Kompatibilität:** Bei Verbindungen werden nur passende Beschriftungsarten verglichen: `self` mit `self`; `additionalLabel` mit `additionalLabel` nur bei gleicher nichtleerer `connectionLabelId`. Nur nutzbare Texte werden in `connectionTextMatrix` bewertet. Unbeschriftete Verbindungen erzeugen **keine** Textpaare.

**Wichtig:** Die Verbindung selbst wird später **im Graph-Matcher** anhand ihrer Identität/Struktur bewertet. Ein identischer Verbindungstext ist nicht automatisch die richtige Linie.

## 5. Ausgabe und Grenzfälle

```text
synonymMatrix[]
  referenceElementId, referenceLabel
  matches[]:
    submissionElementId, submissionLabel
    comparisonBasis, scoreStatus
    scores {methode → rohwert}  ODER  null + unavailableReason

connectionTextMatrix[]
  referenz-/abgabe-Text-ID, zugehörige Connection-IDs,
  kind, connectionLabelId, methodenspezifische scores
```

- Alle zulässigen Fachobjektpaare bleiben in der Matrix. `candidatePairCount = scoredPairCount + unavailablePairCount`.
- `methods` führt Bereiche, Parameter und bei Embeddings Ressourcenmetadaten; der `candidateHash` bindet das vollständige Ergebnis.
- `minimumSimilarity` gehört **nicht** zur Synonym-Berechnung, sondern zur optionalen semantischen Vorschlagslogik des **Graph-Matchers**.
- `not_scored` als spätere Optimierung ist **kein** gegenwärtig aktivierter allgemeiner Trimmingpfad. Nicht berechnet darf künftig nicht mit „unähnlich“ gleichgesetzt werden.

**Workflowparameter:** Mit gesetztem `levenshtein_threshold` friert `workflow-data` `semantics.methods: [levenshtein]` ein; der Dienst berechnet dann nur Levenshtein und lädt kein Embedding-Modell. Mit `text_evidence=tiers` werden stattdessen `damerau_canonical` (Damerau-Levenshtein auf der kanonischen Form: NFC, `Nr.`→`Nummer`, CamelCase/Unterstrich getrennt, casefold, Umlautumschrift ä→ae, Trennzeichen entfernt) und `multilingual_expanded` (NFC, `Nr.`→`Nummer`, CamelCase getrennt) berechnet; `levenshtein_canonical` nutzt dieselbe kanonische Form. Alle drei sind nur auf Anforderung aktiv. Goldkorpus (Stufen 1,0/0,85/0,85): Recall 0,588 → 0,619 bei unveränderten 12 Fehltreffern.

## Kalibrierung Levenshtein (Goldkorpus A1–F2, 257 Fälle)

Erkennung = exakter Anker oder Levenshtein ≥ Schwelle; bewertet nur `equivalent`/`not_equivalent` (160/48).

| Schwelle | Precision | Recall | Fehltreffer (von 48) |
|---|---|---|---|
| 0.70 | 0.81 | 0.41 | 15 |
| 0.75 | 0.83 | 0.38 | 12 |
| 0.80 | 0.86 | 0.31 | 8 |
| 0.85 | 0.88 | 0.19 | 4 |

- **Trägt:** A1–A4 (Groß-/Kleinschreibung nur mit `casefold`), B1 teilweise, D1 bis 0.75, F2 Umlaut/Fugen teilweise.
- **Trägt nicht (Recall ≈ 0):** A7 Abkürzungen, C1/C2 Synonyme, D2 Wortstellung, D4 Paraphrase, D5 Stil, E1/E2 Strukturkontext, F1 Fremdsprache. Hier braucht es andere Verfahren (Token-Sortierung, Embeddings, Kontext).
- **Harte Negative mit hohem Score:** A5 Homophone, A8 Ziffern (`Version 1/2` 0.89), C5 Antonyme mit Präfix (`Anmeldung/Abmeldung` 0.89, `valid/invalid beep` 0.83). Komposita mit anderem Kopf (C4, C7) bleiben unter 0.7.
- **`casefold`** erhöht den Recall bei gleichen Fehltreffern (z. B. 0.80: 0.33 statt 0.31; 0.90: 0.16 statt 0.09).

## Aktuelle Grenze / Veränderungspunkt

> **Zielidee, derzeit nicht umgesetzt:** Günstige exakte Textanker ermitteln und teure Semantik selektiv berechnen. Dabei muss die Menge **aller zulässigen Konkurrenzpaare rekonstruierbar** bleiben. Ein Textanker darf nicht schon hier endgültig die globale 1:1-Identität reservieren. Der aktuelle Graph-Matcher validiert eine vollständige Kandidatenmatrix.

## Änderungslandkarte

| Bereich | Maßgebliche Stelle |
|---|---|
| Vergleichsbereiche / Scoring-Matrix | `dagu/workflow-services/synonym-matching/src/synonym_matching/service.py` · `compare_pair()` |
| Methoden / Normalisierung / Embedding | `synonym_matching/methods/`, `preprocessing.py`, `config.py` |
| Eingabe, Hash, Publikation | `synonym_matching/inventories.py`, `workflow.py`, `provenance.py` |
| Service-Einstieg / Workflow | `synonym-matching/src/main.py`, Dagu `synonym-matching-pair` |
| Tests | `synonym-matching/tests/test_service.py` |

**Änderungsregel:** Text-Evidenz erweitern ja; Identitäts-/Strukturentscheidungen bleiben ausschließlich beim Graph-Matcher.
