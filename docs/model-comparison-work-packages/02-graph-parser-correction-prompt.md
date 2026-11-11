# Korrekturprompt für die bereits umgesetzte Parser-Aufgabe

**Historischer, bereits umgesetzter Korrekturauftrag:** Die allgemeine Parserkorrektur ist abgeschlossen. Nachfolgend wurden Modeling-Layer-Abgrenzung, Parent-Auflösung, kompakte Zugehörigkeitskanten und referenzierte Folgeartefakte umgesetzt. Maßgeblich für neue Arbeiten sind [Paket 02](02-graph-parser.md) und die [gemeinsamen Verträge](README.md). Den früheren Auftrag nicht als offene Neuimplementierung oder Freigabe zum Zurücksetzen späterer Änderungen behandeln. Die aktuelle Laufzeitfunktion ist nicht verifiziert.

---

Bitte korrigiere deine Umsetzung von Arbeitspaket 02 entsprechend der jetzt präzisierten Anforderung. Lies dazu die aktualisierte `docs/model-comparison-work-packages/README.md` und `docs/model-comparison-work-packages/02-graph-parser.md`.

## Verbindliches Ziel

Der Graph-Parser muss allgemein für jede Aufgabe, studentische Abgabe und Sample Solution im vorhandenen Modellformat funktionieren. Die Struktur und die jeweils mitgelieferten, versionierten Sprachdefinitionen sind seine Grundlage. Es darf keine speziell für UML-Klassendiagramme oder irgendeine andere einzelne Modellierungssprache entwickelte Verarbeitung geben. Auch eine bislang nicht fest im Code bekannte Sprachdefinition muss ohne manuelles Freischalten ihrer Typen verwendbar sein.

Diese Korrektur ersetzt die frühere Vorgabe eines UML-Pilotprofils. Alle Formate bleiben V1; bestehende Entwicklungsdefinitionen dürfen direkt angepasst werden. Andere Nutzeränderungen und die bereits umgesetzte allgemeine Eingabe-/Laufzuordnung aus Schritt 01 sind zu bewahren.

## Konkret zu korrigieren

1. **Sprachspezifische Implementierung entfernen.** In `dagu/workflow-services/graph-parser/src/parser.py` sind insbesondere `PROFILE = "uml-class-comparison/v1"`, `UML_RESOURCE_HASH`, `UML_TYPES`, `ATTRIBUTE`, `VISIBILITY` und die damit verbundenen Sonderpfade zu bereinigen. Keine bestimmte Seed-Datei, Sprachversion, Aufgaben-ID oder Sample Solution anhand eines festen Hashes oder Namens besonders behandeln. Nicht durch weitere Sonderfälle für andere Sprachen ersetzen.
2. **Kein Pflichtprofil als Ersatz.** Eine manuell einzutragende `typeMappings`-Liste oder ein pro Sprache auszuwählender Adapter ist keine allgemeine Lösung. `comparisonConfig: {}` muss für die allgemeine Strukturüberführung genügen. Zusätzliche Parameter nur bei belegtem allgemeinen Bedarf vorsehen und dann dokumentieren; keine vorab vollständige Konfigurationsstruktur entwickeln.
3. **Typen und Definitionen allgemein erhalten.** Modelltyp, Sprachversion und konkrete Definition beziehungsweise Definitionenkandidaten aus dem jeweiligen Modellsnapshot auflösen. Typidentität ist durch Sprache/Definition eingegrenzt; gleichnamige Typen verschiedener Sprachen sind nicht automatisch gleich. Eine aufgelöste Definition darf nicht nur wegen einer fehlenden zusätzlichen Übersetzungsregel `unsupported` oder `type: null` werden. Eine unbekannte oder mehrdeutige Definition bleibt mit ihren belastbar bekannten Angaben und einer neutralen Diagnose erhalten.
4. **Keine fachliche Textgrammatik.** Freie Labels unverändert erhalten. Keine UML-Attributzeilen, Methoden, Sichtbarkeit oder andere sprachspezifische Syntax parsen; keine Attributknoten aus solchen Textannahmen erzeugen. Bereits eigenständige Modellzellen und explizit strukturierte Angaben bleiben allgemein als Bestandteile erhalten. Keine Sonderkonvertierungen für einzelne Feldnamen, Sichtbarkeitssymbole, `?` oder vermutete Kardinalitätsformate ohne eindeutige vorhandene Datendefinition. Nicht zerlegter Text ist allein kein Interpretationsfehler.
5. **Allgemeine Struktur beibehalten.** Rekursive Zugehörigkeiten, einheitliche Beziehungsknoten und Anschlüsse, Originalknoten-IDs, Herkunft, native Eigenschaften sowie gerichtete/ungerichtete Beziehungen weiterhin erhalten. Nachfolgend präzisiert: Canvas-Wurzel und Layer bleiben außerhalb des Graphen; fachliche Zwischencontainer innerhalb des Modeling-Layers bleiben erhalten. `contains` verwendet den kompakten Vertrag ohne zusätzliche ID oder Herkunftskopie. Deklarierte Childs werden im Parent-Kontext aufgelöst; tatsächlich unauflösbare Childs bleiben diagnostiziert. Rollen nicht anhand bestimmter Sprachnamen oder Beispieltypen erraten.
6. **Sprachherkunft und Diagnosen beibehalten.** `language`, `languageResolution`, `definition` und `definitionCandidates` bleiben für Elemente und modellierte Beziehungen vorgesehen. Andere erkannte Sprachen sind neutral zu erhalten. Eine bekannte weitere Sprache oder ein fehlendes nicht erforderliches Sprachprofil macht die Interpretation nicht unvollständig. Tatsächlich unklare Herkunft oder Definitionen bleiben lokalisierte Diagnosen. Der Parser entscheidet nicht über die Zulässigkeit der Sprachwahl und erzeugt weder Feedback noch Bewertung.
7. **Direkte Verbraucher konsistent nachziehen.** Nur die durch die Korrektur tatsächlich betroffenen Übergaben, Hashgrundlagen, Schemabeschreibungen und Dokumentationen anpassen. Sprachspezifische `normalizationProfile`-/`profileHash`-Pflichten entfernen, soweit sie allein aus der verworfenen Spezialisierung entstanden sind. Keine pauschale Löschung allgemeiner Provenienz- oder Hashlogik. Die vorhandenen nicht sprachspezifischen Änderungen erhalten; keine ungefragten Refactorings oder neuen Libraries.

## Aktuell ausdrücklich keine Tests oder Ausführung

Keine Tests erstellen, erweitern oder ausführen. Keine manuellen Beispielmodelle parsen, keine Container oder Services starten, keine Smoke-Tests, Benchmarks, Builds, Lint- oder Syntaxprüfungen durchführen. Auch keine angeblich nur kurz notwendige Ausführung zur Verifikation. Zulässig sind Lesen, Bearbeiten und statische Durchsicht der Änderungen.

Vorhandene fachlich unabhängige Tests und andere Nutzeränderungen nicht pauschal löschen. Falls du ausschließlich für die verworfene Spezialisierung neue Hilfs-/Testartefakte angelegt hast, entferne nur diese eindeutig zuordenbaren Ergänzungen, ohne sie vorher erneut auszuführen. Historische Prüfberichte nicht als Nachweis für die jetzt geänderte allgemeine Lösung ausgeben.

## Erwartetes Ergebnis

- Derselbe Parserpfad arbeitet auf den bereitgestellten Daten jeder Aufgabe und ihrer Sample Solutions, ohne fest eingebautes Wissen über einzelne Modellierungssprachen.
- Keine sprachspezifische Typfreischaltung, Profilpflicht oder Labelgrammatik bleibt Voraussetzung.
- Struktur, Identitäten, Eigenschaften und Sprachherkunft bleiben erhalten; echte Unklarheiten werden neutral dokumentiert.
- Schnittstellen und Dokumentation passen zum korrigierten V1-Vertrag.
- Die Zusammenfassung nennt die entfernten Spezialisierungen, die erhaltene allgemeine Verarbeitung und die tatsächlich geänderten Dateien. Sie stellt ausdrücklich fest, dass keine Tests oder Probeläufe ausgeführt wurden und die Laufzeitfunktion dieser Korrektur noch ungetestet ist.

Bitte diese Korrektur umsetzen und nicht nur einen weiteren Plan dafür erstellen.
