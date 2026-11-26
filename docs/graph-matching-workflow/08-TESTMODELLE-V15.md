# 08 · Testmodelle Synonymprüfung 2 (Migration v15)

> **Testdaten** · Stand 17.11.2026 · Migration `15_laboratory_synonym_models` · Aufgabe Laborverwaltung,
> Referenz ist die unveränderte Musterlösung. Erzeugt mit einem einmaligen Generator; die Modelle sind
> danach normale Abgaben im Editor.

## Zweck

Die Modelle aus v12 und v14 übernehmen die Musterlösung und ändern einzelne Beschriftungen oder
Strukturen. Dabei bleibt so viel Struktur erhalten, dass der Graph-Matcher die meisten Objekte über
unveränderte Attribute und Kanten findet und die Textevidenz kaum entscheidet. Die Abgaben S01–S06
sind dagegen eigenständig modelliert:

- **Objekt- und Attributevidenz sind entkoppelt.** Wo ein Objekt umbenannt ist, sind auch seine Attribute
  umbenannt oder verändert, damit es nicht über unveränderte Kinder gefunden wird. Umgekehrt gibt es
  **B-Fälle** (Objektname falsch oder fremd, Attribute exakt) und **A-Fälle** (Objektname exakt,
  Attribute falsch), damit beide Richtungen sichtbar werden.
- **Jede Kategorie A1–F2 des Goldkorpus kommt mindestens einmal vor**, eingebettet in eine realistische
  Abgabe statt als isoliertes Paar.
- **Typische Studentenfehler** verändern die Struktur: fehlende und zusätzliche Kanten, umgekehrte
  Richtung, Objekt als Attribut aufgelöst, Instanzen statt Typen, falscher Typ, verschobene Attribute,
  vertauschte Beschriftungen, Vererbung statt einfachem Typ.
- Verbindungen tragen keine Beschriftung; ihre Zuordnung folgt allein aus den Endpunkten.

## Lesart der Erwartungen

- **gleichwertig**: soll als Gegenstück erkannt werden (Text darf entscheiden).
- **teilweise**: didaktische Entscheidung (Oberbegriff, Zusammenfassung); weder als Fehler noch als
  eindeutige Erkennung werten.
- **kein Gegenstück**: darf keinem Referenzobjekt zugeordnet werden; Fehlzuordnungen hier sind die
  wichtigsten Fehler.
- **nur strukturell**: Gegenstück ergibt sich aus Struktur und Attributen, die Beschriftung weicht ab;
  Textevidenz darf hier keine eindeutige Identität begründen, ein `label.*`-Befund ist erwartet.
- Attributzeilen (↳) nennen nur die Fälle mit Testzweck; nicht aufgeführte Attribute sind exakt oder
  folgen ihrem Objekt.

## S01 · Schreibweisen

Orthografie A1-A4, A6, A8, F2: Großschreibung, Bindestriche, Tippfehler, Umlautumschrift, Schweizer ß, nummerierte E-Mail; Größe beim Gebäude, Laborraum-Ausstattung-Kante fehlt, Arbeitseinsatz unvollständig.

| Abgabe | Erwartetes Gegenstück | Erwartung | Kategorie | Hinweis |
|---|---|---|---|---|
| **GEBÄUDE** | Gebäude | gleichwertig | A1 | nur Großschreibung |
| ↳ GEBÄUDE/Grösse | Laborraum/Größe | gleichwertig | A6 | Besitzer falsch (Gebäude statt Laborraum) |
| **Etage** | Etage | gleichwertig | - | exakter Anker |
| ↳ Etage/Gebäude Nr. | Etage/GebäudeNr. | gleichwertig | A3 |  |
| **Labor-Raum** | Laborraum | gleichwertig | A3 | Bindestrich; Größe fehlt hier |
| ↳ Labor-Raum/RaumNr | Laborraum/RaumNr. | gleichwertig | A2 |  |
| **Geraete** | Geräte | gleichwertig | F2 | Umlaut als ae |
| ↳ Geraete/Geraete-Nr. | Geräte/GeräteNr. | gleichwertig | F2+A2 |  |
| ↳ Geraete/Bezeichung | Geräte/Bezeichnung | gleichwertig | A4 |  |
| **Laborausstattung** | Laborausstattung | gleichwertig | - | Zeilenumbruch wie Referenz; Kante vom Laborraum fehlt |
| ↳ Laborausstattung/Anzhal | Laborausstattung/Anzahl | gleichwertig | A4 |  |
| **Forschungprojekt** | Forschungsprojekt | gleichwertig | F2/A4 | Fugen-s fehlt |
| **Wissenschaftler** | Wissenschaftler | gleichwertig | - | exakter Anker |
| ↳ Wissenschaftler/E-Mail 1 | Wissenschaftler/E-Mail | gleichwertig | A8 | konkurriert mit E-Mail 2 |
| ↳ Wissenschaftler/E-Mail 2 | – | kein Gegenstück | A8 | Zusatzattribut |
| **Projekt Beteiligung** | Projektbeteiligung | gleichwertig | A3 | getrennt geschrieben |
| **versuch** | Versuch | gleichwertig | A1 | kleingeschrieben |
| **Arbeitseinsatz** | Arbeitseinsatz | gleichwertig | - | exakter Anker; ProjektNr., GebäudeNr., EtagenNr. fehlen |

Verbindungen: GEBÄUDE → Etage (1-n), Etage → Labor-Raum (0-n), Geraete → Laborausstattung (0-n), Labor-Raum → Arbeitseinsatz (0-n), Wissenschaftler → Arbeitseinsatz (0-n), Wissenschaftler → Projekt Beteiligung (0-n), Forschungprojekt → Projekt Beteiligung (0-n), Forschungprojekt → versuch (0-n), versuch → Arbeitseinsatz (0-n).

## S02 · Eigene Fachbegriffe

Lexik und Morphologie B1, B2, C1, C2, C3, D4, E2, E4: fast keine exakten Beschriftungen, Attribute ebenfalls umbenannt; Beteiligung als ER-Typ, Projekt-Experiment-Kante fehlt, zusätzliche Kante Gerät-Experimente.

| Abgabe | Erwartetes Gegenstück | Erwartung | Kategorie | Hinweis |
|---|---|---|---|---|
| **Gebäude** | Gebäude | gleichwertig | - | einziger exakter Objektanker |
| ↳ Gebäude/Gebäudekennung | Gebäude/GebäudeNr. | gleichwertig | C2 |  |
| ↳ Gebäude/Name | Gebäude/Bezeichnung | gleichwertig | C1 |  |
| **Stockwerk** | Etage | gleichwertig | C1 |  |
| ↳ Stockwerk/Stockwerksnummer | Etage/EtagenNr. | gleichwertig | C1+A7 |  |
| **Laborräume** | Laborraum | gleichwertig | B1 | Plural mit Umlaut |
| ↳ Laborräume/Raumnummer | Laborraum/RaumNr. | gleichwertig | A7 |  |
| ↳ Laborräume/Fläche | Laborraum/Größe | gleichwertig | C1/C3 |  |
| **Gerät** | Geräte | gleichwertig | B1 | Singular |
| ↳ Gerät/Inventarnummer | Geräte/GeräteNr. | gleichwertig | C2 |  |
| ↳ Gerät/Gerätename | Geräte/Bezeichnung | gleichwertig | E2 |  |
| **ausgestattetmit** | Laborausstattung | gleichwertig | E4 | Verbphrase statt Substantiv |
| ↳ ausgestattetmit/Stückzahl | Laborausstattung/Anzahl | gleichwertig | C1 |  |
| **Projekt** | Forschungsprojekt | teilweise | C3/D3 | Oberbegriff, Kontext eindeutig |
| ↳ Projekt/Projektnummer | Forschungsprojekt/ProjektNr. | gleichwertig | A7 |  |
| ↳ Projekt/Titel | Forschungsprojekt/Bezeichnung | gleichwertig | C2 | konkurriert mit Titel am Experiment |
| **Forscher** | Wissenschaftler | gleichwertig | C1 |  |
| ↳ Forscher/Personalnummer | Wissenschaftler/PersonalNr. | gleichwertig | A7 |  |
| ↳ Forscher/Familienname | Wissenschaftler/Nachname | gleichwertig | C1 | Konkurrenz Vorname (C7) |
| ↳ Forscher/Mail | Wissenschaftler/E-Mail | gleichwertig | A7 |  |
| **arbeitetmit an** | Projektbeteiligung | gleichwertig | D4 | Paraphrase; Typfehler ER statt R |
| ↳ arbeitetmit an/von | Projektbeteiligung/Beginn | gleichwertig | C2 |  |
| ↳ arbeitetmit an/bis | Projektbeteiligung/Ende | gleichwertig | C2 |  |
| **Experimente** | Versuch | gleichwertig | C1+B1 |  |
| ↳ Experimente/Experimentnummer | Versuch/VersuchsNr. | gleichwertig | C1+A7 |  |
| ↳ Experimente/Titel | Versuch/Bezeichnung | gleichwertig | C2 |  |
| **Einsatzplanung** | Arbeitseinsatz | teilweise | B2/D3 | Ableitung, andere Lesart (Planung) |
| ↳ Einsatzplanung/Einsatznummer | Arbeitseinsatz/EinsatzNr. | gleichwertig | A7 |  |
| ↳ Einsatzplanung/Datum | Arbeitseinsatz/Beginn | teilweise | E3: Beginn und Ende zusammengefasst |  |

Verbindungen: Gebäude → Stockwerk (1-n), Stockwerk → Laborräume (0-n), Gerät → ausgestattetmit (0-n), Laborräume → ausgestattetmit (0-n), Laborräume → Einsatzplanung (0-n), Forscher → Einsatzplanung (0-n), Forscher → arbeitetmit an (0-n), Projekt → arbeitetmit an (0-n), Gerät → Experimente (0-n), Experimente → Einsatzplanung (0-n).

## S03 · Englisch und Sprachmix

Sprache F1 mit D1, D2, C8: englische Objekte und snake_case-Attribute, zwei deutsche Mischbeschriftungen; Wissenschaftler-Einsatz-Kante fehlt, Experiment-Einsatz umgekehrt.

| Abgabe | Erwartetes Gegenstück | Erwartung | Kategorie | Hinweis |
|---|---|---|---|---|
| **Building** | Gebäude | gleichwertig | F1 |  |
| ↳ Building/building_id | Gebäude/GebäudeNr. | gleichwertig | F1+A3 |  |
| ↳ Building/name | Gebäude/Bezeichnung | gleichwertig | F1/C1 | konkurriert mit name am Experiment |
| **Floor** | Etage | gleichwertig | F1 |  |
| ↳ Floor/floor_no | Etage/EtagenNr. | gleichwertig | F1+A7 |  |
| **Lab Room** | Laborraum | gleichwertig | F1 |  |
| ↳ Lab Room/size_sqm | Laborraum/Größe | gleichwertig | F1+D3 |  |
| **Equipment** | Geräte | gleichwertig | F1/C3 | Sammelbegriff |
| ↳ Equipment/label | Geräte/Bezeichnung | gleichwertig | F1 |  |
| **AusstattungLabor** | Laborausstattung | gleichwertig | D2 | Wortstellung, deutsch |
| ↳ AusstattungLabor/quantity | Laborausstattung/Anzahl | gleichwertig | F1 |  |
| **Research Project** | Forschungsprojekt | gleichwertig | F1 |  |
| ↳ Research Project/title | Forschungsprojekt/Bezeichnung | gleichwertig | F1/C2 |  |
| **Scientist** | Wissenschaftler | gleichwertig | F1 |  |
| ↳ Scientist/last_name | Wissenschaftler/Nachname | gleichwertig | F1 | Konkurrenz first_name |
| **Beteiligungam Projekt** | Projektbeteiligung | gleichwertig | D1+F2 | Füllwörter, aufgelöstes Kompositum |
| ↳ Beteiligungam Projekt/start | Projektbeteiligung/Beginn | gleichwertig | F1 |  |
| ↳ Beteiligungam Projekt/end | Projektbeteiligung/Ende | gleichwertig | F1 |  |
| **Experiment** | Versuch | gleichwertig | F1/C1 |  |
| ↳ Experiment/description | Versuch/Beschreibung | gleichwertig | F1 |  |
| ↳ Experiment/name | Versuch/Bezeichnung | gleichwertig | F1 |  |
| **Assignment** | Arbeitseinsatz | gleichwertig | F1/C8 | mehrdeutig (Zuweisung, Aufgabe) |

Verbindungen: Building → Floor (1-n), Floor → Lab Room (0-n), Equipment → AusstattungLabor (0-n), Lab Room → AusstattungLabor (0-n), Lab Room → Assignment (0-n), Scientist → Beteiligungam Projekt (0-n), Research Project → Beteiligungam Projekt (0-n), Research Project → Experiment (0-n), Assignment → Experiment (0-n).

## S04 · Verwechslungsgefahr

Harte Negative A5, A8, C4, C5, C6, C7, C8: Etagen als Instanzen, Geräteraum statt Geräte, Projektantrag, Laborant mit Wissenschaftler-Attributen, Besuch statt Versuch, Eintritt/Austritt; Geräte, Laborausstattung und Versuch fehlen.

| Abgabe | Erwartetes Gegenstück | Erwartung | Kategorie | Hinweis |
|---|---|---|---|---|
| **Gebäude** | Gebäude | gleichwertig | - | exakter Anker |
| ↳ Gebäude/Adresse | – | kein Gegenstück | C6 |  |
| **Etage 1** | Etage | teilweise | A8 | Instanz statt Typ; konkurriert mit Etage 2 |
| ↳ Etage 1/Raumanzahl | – | kein Gegenstück | C6 |  |
| **Etage 2** | – | kein Gegenstück | A8 | zweite Instanz |
| **Laborraum** | Laborraum | gleichwertig | - | A-Fall: exakter Name, Attribute unvollständig |
| ↳ Laborraum/Raumtyp | – | kein Gegenstück | C6 |  |
| **Geräteraum** | – | kein Gegenstück | C4 | anderer Kopf; darf weder Geräte noch Laborraum treffen |
| ↳ Geräteraum/Größe | Laborraum/Größe | nur strukturell | exakt, aber falscher Besitzer |  |
| **Projektantrag** | – | kein Gegenstück | C6 | verwandt, nicht gleich; Forschungsprojekt fehlt |
| ↳ Projektantrag/Leiter | – | kein Gegenstück | C8 |  |
| **Laborant** | Wissenschaftler | nur strukturell | C7 | B-Fall: Attribute exakt, Bezeichnung Kohyponym |
| **Projektbeteiligung** | Projektbeteiligung | gleichwertig | - | exakter Anker |
| ↳ Projektbeteiligung/Eintritt | Projektbeteiligung/Beginn | gleichwertig | C2 | Gegensatzpaar zu Austritt (C5) |
| ↳ Projektbeteiligung/Austritt | Projektbeteiligung/Ende | gleichwertig | C2 | darf nicht Beginn treffen |
| **Besuch** | – | kein Gegenstück | A5/C6 | klangähnlich zu Versuch |
| **Arbeitseinsatz** | Arbeitseinsatz | gleichwertig | - | exakter Anker |

Verbindungen: Gebäude → Etage 1 (1-n), Gebäude → Etage 2 (1-n), Etage 1 → Laborraum (0-n), Etage 2 → Geräteraum (0-n), Laborant → Projektbeteiligung (0-n), Projektantrag → Projektbeteiligung (0-n), Projektantrag → Besuch (0-n), Laborant → Arbeitseinsatz (0-n), Laborraum → Arbeitseinsatz (0-n), Besuch → Arbeitseinsatz (0-n).

## S05 · Granularität und Stil

Struktur und Phrase A7, B2, C3, D1, D3, D4, D5, D6, E2, E3: Etage als Attribut in Raum aufgelöst, Name statt Vor-/Nachname, Zeitraum statt Beginn/Ende, technische und umschreibende Beschriftungen.

| Abgabe | Erwartetes Gegenstück | Erwartung | Kategorie | Hinweis |
|---|---|---|---|---|
| **GebäudeDaten** | Gebäude | teilweise | D6 | technischer Zusatz |
| ↳ GebäudeDaten/Nr | Gebäude/GebäudeNr. | gleichwertig | E2: Kontext weggelassen |  |
| **Raum** | Laborraum | teilweise | C3/D3 | Oberbegriff; Etage-Objekt fehlt |
| ↳ Raum/GebNr | Laborraum/GebäudeNr. | gleichwertig | A7 |  |
| ↳ Raum/Etage | – | nur strukturell | E3: Objekt Etage als Attribut |  |
| ↳ Raum/Fläche in qm | Laborraum/Größe | gleichwertig | D3 |  |
| **Gerätschaften** | Geräte | gleichwertig | B2 | Ableitung |
| ↳ Gerätschaften/GerätNr | Geräte/GeräteNr. | gleichwertig | B1+A2 |  |
| ↳ Gerätschaften/Typenbezeichnung | Geräte/Bezeichnung | teilweise | D3 |  |
| **Ausstattungdes Labors** | Laborausstattung | gleichwertig | D1+F2 | Genitivumschreibung |
| ↳ Ausstattungdes Labors/Menge | Laborausstattung/Anzahl | gleichwertig | C1 |  |
| **Forschungsvorhaben** | Forschungsprojekt | gleichwertig | C1 |  |
| ↳ Forschungsvorhaben/Projekttitel | Forschungsprojekt/Bezeichnung | gleichwertig | E2+C2 |  |
| **Mitarbeiter** | Wissenschaftler | teilweise | C3 | Oberbegriff |
| ↳ Mitarbeiter/PersNr | Wissenschaftler/PersonalNr. | gleichwertig | A7 |  |
| ↳ Mitarbeiter/Name | Wissenschaftler/Nachname | teilweise | E3: Vor- und Nachname zusammengefasst |  |
| **ist beteiligtan** | Projektbeteiligung | gleichwertig | D4/E4 | Verbphrase |
| ↳ ist beteiligtan/Zeitraum | Projektbeteiligung/Beginn | teilweise | E3: Beginn und Ende zusammengefasst |  |
| **Versuchsdurchführung** | Versuch | gleichwertig | D5/B2 | B-Fall: Attribute exakt |
| **Einsatz** | Arbeitseinsatz | gleichwertig | D3/E2 | Kopf ohne Bestimmungswort |
| ↳ Einsatz/Datum | Arbeitseinsatz/Beginn | teilweise | E3 |  |

Verbindungen: GebäudeDaten → Raum (1-n), Gerätschaften → Ausstattungdes Labors (0-n), Raum → Ausstattungdes Labors (0-n), Raum → Einsatz (0-n), Mitarbeiter → Einsatz (0-n), Mitarbeiter → ist beteiligtan (0-n), Forschungsvorhaben → ist beteiligtan (0-n), Forschungsvorhaben → Versuchsdurchführung (0-n), Versuchsdurchführung → Einsatz (0-n).

## S06 · Vertauschungen und Vererbung

Struktur gegen Text E1, C3: Beschriftungen Etage und Laborraum vertauscht, Wissenschaftler als Untertyp einer Person (Attribute am Obertyp), Drittmittelprojekt mit exakten Attributen.

| Abgabe | Erwartetes Gegenstück | Erwartung | Kategorie | Hinweis |
|---|---|---|---|---|
| **Gebäude** | Gebäude | gleichwertig | - | exakter Anker |
| **Laborraum** | Etage | nur strukturell | - | vertauscht: Struktur und Attribute einer Etage |
| **Etage** | Laborraum | nur strukturell | - | vertauscht: Struktur und Attribute eines Laborraums |
| **Geräte** | Geräte | gleichwertig | - | exakter Anker |
| **Laborausstattung** | Laborausstattung | gleichwertig | - | exakter Anker |
| **Drittmittelprojekt** | Forschungsprojekt | teilweise | C3 | B-Fall: Unterbegriff, Attribute exakt |
| **Person** | – | nur strukturell | C3 | Obertyp trägt die Wissenschaftler-Attribute |
| **(Generalisierung)** | – | kein Gegenstück | - | Generalisierung ohne Gegenstück |
| **Wissenschaftlich** | Wissenschaftler | gleichwertig | E1 | Bezeichnung über die Vererbung verteilt |
| ↳ Wissenschaftlich/Fachgebiet | – | kein Gegenstück | zusätzlich |  |
| **Technisch** | – | kein Gegenstück | E1 | zusätzlicher Untertyp |
| ↳ Technisch/Ausbildung | – | kein Gegenstück | zusätzlich |  |
| **Projektbeteiligung** | Projektbeteiligung | gleichwertig | - | exakter Anker |
| **Versuch** | Versuch | gleichwertig | - | exakter Anker |
| **Arbeitseinsatz** | Arbeitseinsatz | gleichwertig | - | exakter Anker |

Verbindungen: Gebäude → Laborraum (1-n), Laborraum → Etage (0-n), Geräte → Laborausstattung (0-n), Etage → Laborausstattung (0-n), Etage → Arbeitseinsatz (0-n), Person → Generalisierung (0-1), Generalisierung → Wissenschaftlich (0-1), Generalisierung → Technisch (0-1), Wissenschaftlich → Arbeitseinsatz (0-n), Wissenschaftlich → Projektbeteiligung (0-n), Drittmittelprojekt → Projektbeteiligung (0-n), Drittmittelprojekt → Versuch (0-n), Versuch → Arbeitseinsatz (0-n).

## Abdeckung der Kategorien

| Kategorie | Fälle |
|---|---|
| A1 Groß-/Kleinschreibung | S01 GEBÄUDE, versuch |
| A2 Sonderzeichen | S01 RaumNr, Geraete-Nr.; S05 GerätNr |
| A3 Getrennt/zusammen | S01 Labor-Raum, Projekt Beteiligung, Gebäude Nr.; S03 building_id |
| A4 Tippfehler | S01 Bezeichung, Anzhal, Forschungprojekt |
| A5 Klangähnlichkeit | S04 Besuch (Versuch) |
| A6 Regionale Schreibung | S01 Grösse |
| A7 Abkürzungen | S02 Raumnummer, Mail; S05 PersNr, GebNr |
| A8 Ziffern | S01 E-Mail 1/2; S04 Etage 1/2 |
| B1 Flexion | S02 Laborräume, Gerät; S05 GerätNr |
| B2 Ableitung | S02 Einsatzplanung; S05 Gerätschaften, Versuchsdurchführung |
| C1 Synonym | S02 Stockwerk, Forscher, Familienname, Stückzahl; S05 Forschungsvorhaben, Menge |
| C2 Domänensynonym | S02 Inventarnummer, Titel, von/bis; S04 Eintritt/Austritt |
| C3 Ober-/Unterbegriff | S02 Projekt; S05 Mitarbeiter, Raum; S06 Drittmittelprojekt, Person |
| C4 Teil-Ganzes | S04 Geräteraum |
| C5 Gegensatz | S04 Eintritt/Austritt |
| C6 Verwandt | S04 Projektantrag, Besuch, Adresse |
| C7 Kohyponym | S04 Laborant; S02 Familienname gegen Vorname |
| C8 Mehrdeutigkeit | S03 Assignment; S04 Leiter |
| D1 Füllwörter | S03 Beteiligung am Projekt; S05 Ausstattung des Labors |
| D2 Wortstellung | S03 Ausstattung Labor |
| D3 Länge/Detail | S05 Fläche in qm, Einsatz, Raum; S03 size_sqm |
| D4 Paraphrase | S02 arbeitet mit an; S05 ist beteiligt an |
| D5 Beschriftungsstil | S05 Versuchsdurchführung |
| D6 Technischer Begriff | S05 GebäudeDaten |
| E1 Vererbung | S06 Person → Wissenschaftlich/Technisch |
| E2 Kontext im Label | S02 Gerätename; S05 Nr, Projekttitel |
| E3 Granularität | S05 Etage als Attribut, Name, Zeitraum; S02 Datum |
| E4 Äquivalente Struktur | S02 ausgestattet mit; S05 ist beteiligt an |
| F1 Fremdsprache | S03 vollständig englisch |
| F2 Deutsche Morphologie | S01 Geraete, Forschungprojekt; S03 Beteiligung am Projekt; S05 Ausstattung des Labors |

## Strukturfehler je Modell

| Modell | Struktur |
|---|---|
| S01 | Kante Laborraum → Laborausstattung fehlt; Größe beim Gebäude; Arbeitseinsatz ohne ProjektNr./GebäudeNr./EtagenNr. |
| S02 | Beteiligung als ER-Typ; Kante Projekt → Experimente fehlt; zusätzliche Kante Gerät → Experimente |
| S03 | Kante Scientist → Assignment fehlt; Assignment → Experiment statt umgekehrt |
| S04 | Etage als zwei Instanzen; Geräte, Laborausstattung, Forschungsprojekt, Versuch fehlen; Geräteraum und Besuch zusätzlich |
| S05 | Etage-Objekt als Attribut im Raum; Gebäude direkt mit Raum verbunden |
| S06 | Etage und Laborraum vertauscht beschriftet; Wissenschaftler über Generalisierung mit Obertyp Person |

## Erstbefund (lokaler Lauf, 17.11.2026)

Lauf der Service-Images ohne Dagu (workflow-data `v3`, graph-parser, model-label-extraction,
synonym-matching `v3`, one-to-one-graph-matching `v7`) gegen die Musterlösung. Gezählt sind die Zeilen der
Tabellen oben: **richtig** (Gegenstück wie erwartet oder zu Recht keins), **falsch** (falsches Gegenstück),
**verfehlt** (erwartetes Gegenstück fehlt). Teilweise-Fälle sind nicht gezählt.

| Modell | Evidenzstufen richtig / falsch / verfehlt | Levenshtein 0,8 richtig / falsch / verfehlt |
|---|---|---|
| S01 Schreibweisen | 11 / 0 / 7 | 10 / 0 / 8 |
| S02 Eigene Fachbegriffe | 5 / 1 / 20 | 5 / 0 / 21 |
| S03 Englisch und Sprachmix | 4 / 0 / 18 | 0 / 0 / 22 |
| S04 Verwechslungsgefahr | 14 / 1 / 1 | 13 / 1 / 2 |
| S05 Granularität und Stil | 5 / 0 / 8 | 2 / 0 / 11 |
| S06 Vertauschungen und Vererbung | 9 / 2 / 1 | 9 / 2 / 1 |

Aufgedeckte Schwächen:

1. **Attribute semantisch erkannter Objekte bleiben offen.** `Labor-Raum/RaumNr` ↔ `Laborraum/RaumNr.` hat
   kanonisch 1,0, wird aber mit `owner_unresolved` zurückgestellt: Die semantische Verfeinerung ist ein
   einzelner Durchlauf und akzeptiert nur exakt verankerte Besitzer. Fast alle umbenannten Attribute sind
   deshalb verfehlt (S01–S03, S05).
2. **Bedeutungsstufe:** `arbeitet mit an` → `Arbeitseinsatz` (Embedding 0,88) ist ein Fehltreffer mit
   eindeutiger Identität; `Lab Room` (0,76), `Equipment` (0,84) und `Stockwerk` (0,67) bleiben darunter.
3. **Fehlende Umformungen:** weicher Zeilenumbruch (`Wissen\nschaftler` ↔ `Scientist`), Umlautumschrift
   (`Geraete` ↔ `Geräte` 0,71), Buchstabendreher (`Anzhal` ↔ `Anzahl` 0,67).
4. **Struktur gegen Text:** In S06 gewinnen die vertauschten exakten Beschriftungen die Zuordnung
   (Identität bleibt `unresolved`); in S04 wird `Geräteraum` über unabhängige Kinder (`GebäudeNr.`,
   `RaumNr.`) der `Laborausstattung` zugeordnet.
5. **Korrekt abgelehnt:** `Besuch`, `Projektantrag`, `Etage 2`, `Technisch`, `E-Mail 2`; `Grösse` am
   Gebäude erreicht kanonisch 1,0, wird wegen des Besitzerkonflikts aber zu Recht nicht vorgeschlagen.

## Ergebnis nach Umsetzung der fünf Vorschläge (17.11.2026)

Graph-Matcher `2.5.0` (Image `v9`), Synonymdienst `1.3.0` (`v4`), workflow-data `v4`. Gleiche Zählung wie
im Erstbefund (richtig / falsch / verfehlt).

| Modell | Stufen vorher | Stufen jetzt | Levenshtein 0,8 vorher | Levenshtein 0,8 jetzt | ohne Text jetzt |
|---|---|---|---|---|---|
| S01 | 11 / 0 / 7 | **15 / 0 / 3** | 10 / 0 / 8 | 11 / 0 / 7 | 7 / 0 / 11 |
| S02 | 5 / 1 / 20 | 6 / 1 / 19 | 5 / 0 / 21 | 5 / 0 / 21 | 3 / 0 / 23 |
| S03 | 4 / 0 / 18 | **8 / 0 / 14** | 0 / 0 / 22 | 0 / 0 / 22 | 0 / 0 / 22 |
| S04 | 14 / 1 / 1 | 14 / 1 / 1 | 13 / 1 / 2 | **14 / 0 / 2** | 14 / 0 / 2 |
| S05 | 5 / 0 / 8 | 6 / 0 / 7 | 2 / 0 / 11 | 2 / 0 / 11 | 2 / 0 / 11 |
| S06 | 9 / 2 / 1 | **9 / 0 / 3** | 9 / 2 / 1 | **9 / 0 / 3** | 9 / 0 / 3 |

Regression gegen den Stand vor der Umsetzung (60 Läufe: v12, v14, v15 je in drei Modi): **v14 unverändert**,
**v12 nur Gewinne** (z. B. `Gebaeude` → `Gebäude`, `laborRaum/Groesse` → `Laborraum/Größe`, alle über gleiche
Zell-IDs geprüft), v15 verliert nur die beabsichtigten Fehlzuordnungen (`Geräteraum` → `Laborausstattung`,
vertauschte `Etage`/`Laborraum`).

Offen und bewusst nicht weggeregelt:
- `arbeitet mit an` → `Arbeitseinsatz` (S02, Embedding 0,88, eindeutig); seine Substruktur-Kinder folgen dem
  falschen Besitzer. Fall für Guards bzw. Prüfung durch Menschen.
- `Projektantrag` → `Forschungsprojekt` (S04) als nur „gestützter“ Graubereichsvorschlag: Text ≥ 0,70 und
  Nachbar `Projektbeteiligung` sprechen dafür, das Projekt fehlt in der Abgabe.
- Vorschlag 2 als reine Seltenheitsregel hätte `Bauwerk` und `Apparate` (v14 M02) verloren; umgesetzt ist
  stattdessen GM-07a (eindeutige Konfliktkinder blockieren).
- Zeilenumbruch für Embeddings (`Wissen\nschaftler` ↔ `Scientist`) wartet auf die Sprachannotation.
