# Konzept für In-App-Onboarding und Product Tours

## Status und Geltungsbereich

Dieses Dokument beschreibt den analysierten Ist-Zustand und ein Umsetzungskonzept. Es enthält bewusst keine Implementierung. Insbesondere wurden keine Tour-Library, Selektoren, Abhängigkeiten oder Konfigurationen ergänzt.

Die Analyse basiert auf dem aktuellen Web-Client unter `web/src`, den zugehörigen API-Typen und den für Authentifizierung und Benutzerbezug relevanten Backend-Routen unter `api/src/modeling_api`.

## Kurzfazit

Modeling Copilot ist kein klassisches Dashboard, sondern ein rollenabhängiger, versionierter Modellierungsarbeitsplatz. Die Route `/` ist der persönliche Modellkatalog. Der wichtigste Endnutzer-Workflow ist:

1. ein freies Modell oder ein Modell aus einer veröffentlichten Aufgabe anlegen,
2. dem freien Modell mindestens eine veröffentlichte Modellierungssprache zuordnen,
3. Elemente per Drag-and-drop auf die Zeichenfläche setzen,
4. Verbindungen aus einer Palette auswählen und im Modell verwenden,
5. Änderungen als Checkpoint speichern und bei Bedarf als Release veröffentlichen.

Für Administratoren kommen zwei eigene Kernprozesse hinzu: Modellierungssprachen definieren und versionieren sowie Aufgaben erstellen, mit Sprach-Releases und Musterlösungen verknüpfen und veröffentlichen.

Eine einzige globale Tour wäre ungeeignet. Empfohlen werden kurze, route-lokale Touren mit einem klaren Nutzungsmoment. Das First-Time-Onboarding bleibt bei vier Schritten; die eigentliche Modellierung wird erst nach Öffnen des ersten Modells erklärt.

## 1. Analyse des bestehenden Projekts

### 1.1 Architektur und UI-Rahmen

- Vue 3 mit Composition API und TypeScript, gebaut mit Vite.
- Vuetify 3 stellt App-Bar, Karten, Dialoge, Tabs, Tabellen, Menüs, Expansion Panels, Formulare und Snackbars bereit.
- Pinia verwaltet Benutzer-, Modellierungs- und Sprachzustand.
- Vue Router verwendet `createWebHashHistory`; fachliche Pfade erscheinen daher technisch unter einem Hash.
- maxGraph bildet die Zeichenfläche, Zellen, Verbindungen, Auswahl, Undo/Redo, Zoom und XML-Persistenz ab.
- `App.vue` enthält global `HeaderMain`, `RouterView`, `FooterMain` und `AppNotification`.
- Seiten werden im Router lazy geladen. Eine Tour darf deshalb weder unmittelbar nach `router.push` noch allein nach `onMounted` auf ein Zielelement zugreifen.

Es gibt derzeit keinen Tour-Service, keinen Tour-Store und keine semantischen Tour-Anker. Einige verständliche CSS-Klassen und wenige fachliche IDs existieren, sind aber nicht als dauerhafte Integrationsschnittstelle gedacht.

### 1.2 Routen und tatsächliche Benutzerführung

| Route | View | Zugriff | Rolle im Produkt |
| --- | --- | --- | --- |
| `/login` | `ViewLogin.vue` | öffentlich | Eingabe und Prüfung eines extern erzeugten Bearer-Tokens |
| `/` | `ViewHome.vue` | authentifiziert | persönlicher Modellkatalog und tatsächliche Startseite |
| `/modeling/:modelId?` | `ViewModeling.vue` | authentifiziert | Modellierungsarbeitsplatz |
| `/diagramLanguages` | `ViewDiagramLanguageOverview.vue` | nur `ADMIN` durch Router-Guard | Sprachkatalog, Versionen, Testen und Forken |
| `/diagramLanguageEditor/:id?` | `ViewDiagramLanguageEditor.vue` | nur `ADMIN` durch Router-Guard | Sprachdefinition für Elemente, Verbindungen, Syntax und Feedback |
| `/tasks` | `ViewTaskEditor.vue` | nur `ADMIN` durch Router-Guard | Aufgaben erstellen, versionieren und veröffentlichen |
| `/404` | `View404Page.vue` | authentifiziert | fehlende Route oder fehlende Berechtigung |

Wichtige Beobachtungen:

- Es existiert keine separate Dashboard-Route. In Tourtexten sollte deshalb von „Meine Modelle“ oder „Modellkatalog“, nicht von „Dashboard“, gesprochen werden.
- Die Header-Navigation zeigt `Languages` und `Editor` derzeit auch Nicht-Administratoren, obwohl der Router sie anschließend auf `/404` leitet. Eine Tour darf diese Einträge für Nicht-Administratoren nicht hervorheben.
- Der direkte Header-Link `/diagramLanguageEditor` enthält keine Sprach-ID. Die View bleibt dann ohne geladene Sprachdefinition. Eine Editor-Tour darf nur auf `/diagramLanguageEditor/:id` starten.
- Der Logout-Button navigiert nur nach `/login`; er entfernt das Token nicht. „Erster Login“ kann daher nicht zuverlässig aus dem Navigationsereignis abgeleitet werden.

### 1.3 Authentifizierung, Rollen und Berechtigungen

- Das Projekt besitzt keine Registrierung und keinen Passwort-Login. Es erwartet ein JWT eines externen Systems.
- Das Token liegt unter `token` in `localStorage` und wird durch den Axios-Interceptor als Bearer-Token gesendet.
- `/auth/validate` prüft das Token; `/auth/me` liefert die Claims.
- `userStore.ts` hält nur `userId`, `globalRole` und einen `loaded`-Status im Arbeitsspeicher.
- `GlobalRoles.ts` kennt `ADMIN`, `EDITOR` und `VIEWER`. In der aktuellen Frontend-Navigation wird jedoch nur zwischen `ADMIN` und „nicht ADMIN“ unterschieden.
- `courseRoles` ist im Token-Typ vorgesehen, wird im Web-Client aber nicht für Sichtbarkeit oder Routing ausgewertet.
- Modelle gehören dem angemeldeten Benutzer. Aufgaben sind für Nicht-Administratoren nur sichtbar, wenn sie veröffentlicht sind. Sprach- und Aufgabenverwaltung sind im Frontend Admin-Bereiche.

Folgerung für Touren: Zielgruppen und Schritte werden gegen die tatsächlich wirksame Rolle geprüft. Eine Tour darf nicht allein anhand sichtbarer Header-Buttons annehmen, dass eine Route erlaubt ist.

### 1.4 State Management und Persistenz

`useModelWorkspaceStore` ist das Zentrum des Modellierungsworkflows. Er verwaltet unter anderem:

- das Modell und seine aktuelle Basisversion,
- Checkpoints, Releases und lokale Patches,
- ausgewählte Sprach-Releases,
- aufgelöste Sprachdefinitionen,
- Modellpräferenzen,
- Aufgabenreferenz, Aufgabenversion und Task Edits,
- Sync-Zustände `synced`, `dirty`, `saving`, `offline` und `conflict`,
- lokale Recovery-Drafts.

`useDiagramLanguageStore` verwaltet die geladene Sprache, die unveränderliche Version, Dirty-State, Restore und Save/Release. `useUserStore` ist nicht persistent. `useToolManagementStore` ist ein kleiner UI-Store für ausgewählte Entitäten und einen Attributdialog.

Die bereits vorhandenen `Model.preferences` sind pro Modell gespeichert und werden aktuell für Favoriten und zuletzt verwendete Verbindungen genutzt. Sie sind nicht als globale Benutzerpräferenzen geeignet. Das Backend besitzt derzeit weder eine Benutzer-Collection noch einen User-Preferences-Endpunkt.

### 1.5 Kernworkflows

#### Persönlicher Modellkatalog

`ViewHome.vue` lädt serverseitig paginierte Modelle und bietet:

- Tabs für freie Modelle, Aufgabenmodelle und Archiv,
- Suche und Sortierung,
- „New Model“ für ein zunächst leeres Modell ohne Sprache,
- „From task“ für ein Modell aus einer veröffentlichten Aufgabenversion,
- Öffnen, Umbenennen, Archivieren und Wiederherstellen,
- aufgeklappte Releases und alle Saves,
- Vorschau und „Use as new model“ als Branch.

Der größte Discovery-Risikopunkt: Ein freies neues Modell wird mit leerer Sprachliste erzeugt. Ohne das spätere Öffnen von „Languages“ in der rechten Sidebar enthält die linke Elementpalette keine nutzbaren Elemente.

#### Modellierungsarbeitsplatz

`ViewModeling.vue` bettet `DrawingCanvas.vue` ein. Der Workspace besteht aus:

- `ModelingHeader`: Modellname, Checkpoint, Release, Timeline, Undo/Redo und Autonomy-Modus,
- `CanvasToolbar`: Layer, Verbindungspalette, Auswahl-, Lösch-, Duplizier- und Ausrichtungsfunktionen,
- linker `ElementsSidebar`: Suche, Darstellungsmodi und eingeklappte Sprachgruppen; Elemente werden per Drag-and-drop erzeugt,
- zentralem maxGraph-Canvas mit Zoom, Grid, Settings und Shortcut-Hilfe,
- rechter Sidebar: Task Edits, Feedback, Import/Export, Sync und Sprachen,
- optionaler Aufgabenleiste mit Aufgabeninhalt, Edit-Modus und frei schwebendem Fenster,
- optionalen Musterlösungen,
- Recovery- und Vorschau-Dialogen.

Erklärungsbedürftig sind vor allem Sprachzuordnung, Drag-and-drop, Verbindungspalette, der Unterschied zwischen Checkpoint und Release, die Timeline sowie die beiden Ebenen Modell/Feedback. Reine Zoom- oder Ausrichtungsbuttons sind durch Icons und Tooltips hinreichend selbsterklärend.

#### Sprachkatalog und Spracheditor

Admins verwalten im Sprachkatalog Identität, Archiv, Releases, alle Saves, Testläufe und Forks. Der Spracheditor arbeitet in fünf Tabs:

- `Elements`: Liste, umfangreiches Eigenschaftenformular, Live-Vorschau,
- `Connections`: Liste, Basic/Advanced/Expert-Konfiguration, verschiedene Vorschau-Szenarien,
- `Syntax`: Verbindungsmatrix, Kardinalitäten und Vorschau in verschiedenen Feedback-Modi,
- `Feedback`: Overlay-Ziele sowie eigene Feedback-Elemente und Regeln,
- `Settings`: aktuell deaktiviert.

Die wiederkehrende Drei-Spalten-Struktur „Entität wählen – konfigurieren – live testen“ ist tourwürdig. Die Detailformulare sind zu groß für eine lineare Volltour; Syntax und Feedback benötigen eigene, kontextuelle Touren.

#### Aufgabeneditor und Aufgabenmodell

Admins verwalten Aufgaben in einer Master-Detail-Ansicht. Eine Aufgabe kombiniert:

- Name, Eigentümer, privat/veröffentlicht und Archivstatus,
- feste Sprach-Releases,
- einen Modellierungs- bzw. Feedbackmodus,
- optionale Modell-Releases als Musterlösungen,
- einen Rich-Text-Aufgabentext mit Referenzen auf Elemente und Verbindungen,
- Checkpoints, Releases und Branches.

Beim Bearbeiten eines Aufgabenmodells sind die zugeordneten Sprachen erforderlich und nicht austauschbar. Der Modus ist durch die Aufgabe gesperrt. Lernende können den Aufgabentext optional mit Task Edits formatieren oder ergänzen; diese Edits werden separat synchronisiert und in Modellversionen als Snapshot erfasst.

### 1.6 Dynamische und bedingte UI-Zustände

- Sprachgruppen in `ElementsSidebar` sind standardmäßig geschlossen.
- Die Verbindungspalette existiert nur, wenn mindestens eine Verbindung geladen ist.
- Der Task-Tab rechts und die Aufgabenleiste existieren nur bei aufgabengebundenen Modellen.
- „Sample solutions“ existiert nur, wenn die Aufgabenversion Referenzen enthält.
- Release ist erst möglich, wenn ein Modell existiert, ein Checkpoint gespeichert ist, keine lokalen Patches ausstehen und der Sync-Zustand `synced` ist.
- Erforderliche Aufgabensprachen können nicht entfernt oder auf eine andere Version umgestellt werden.
- Syntax-Konfiguration setzt Elemente voraus; sinnvolle Verfeinerungen setzen zusätzlich Verbindungen voraus.
- Feedback-Ziele entstehen erst aus vorhandenen Elementen und Verbindungen.
- Dialoge und Menüs von Vuetify werden typischerweise per Teleport außerhalb des lokalen Komponentenbaums gerendert.
- Modell- und Sprachlisten sowie Versionen werden asynchron geladen.
- Recovery, Konflikte und Offline-Zustände können den normalen Ablauf überlagern.

### 1.7 Responsive Verhalten

Die Anwendung ist primär für Desktop-Nutzung ausgelegt:

- Header-Gruppen umbrechen teilweise unter 900 px.
- Die Verbindungspalette reduziert unter 600 px Beschriftungen und Spalten.
- Einzelne Dialog-Grids wechseln unter 700 px auf eine Spalte.
- Zeichenfläche und Admin-Editoren behalten jedoch feste beziehungsweise parallele Sidebars und Drei-Spalten-Layouts.
- Der Task-Editor besitzt eine mindestens 260 px breite Seitenleiste und kein mobiles Gesamtlayout.
- `ViewModeling` erzwingt eine Mindesthöhe von 900 px.

Angeheftete Desktop-Touren sollten unter einer Mindestbreite von etwa 1024 px nicht automatisch starten. Auf kleineren Viewports ist ein nicht angehefteter Hinweis „Für die Modellierung Desktop verwenden“ sinnvoller als eine fehleranfällige Tour.

## 2. Leitlinien für das Tour-System

1. **Route-lokal statt app-weit:** Keine Tour führt automatisch über mehrere Routen. Ein Abschluss-CTA kann zur nächsten Route führen und dort eine neue Tour freischalten.
2. **Kurz und aufgabenzentriert:** Vier bis sechs Schritte pro Tour. Ein Schritt erklärt eine Entscheidung oder Handlung, keine vollständige Oberfläche.
3. **Keine unerwarteten Mutationen:** Touren archivieren, importieren, speichern, veröffentlichen oder erstellen nichts selbst.
4. **Interaktion nur kontrolliert:** Menüs, Tabs oder Dialoge dürfen für einen Erklärschritt geöffnet werden. Nutzdaten werden nicht verändert; zuvor vorhandener UI-Zustand wird anschließend wiederhergestellt.
5. **Bedingte Schritte:** Nicht vorhandene Verbindungen, Musterlösungen oder Task Edits führen zum Überspringen des betroffenen Schritts, nicht zum Abbruch der ganzen Tour.
6. **Semantische Ziele:** Spätere Implementierung über dedizierte Tour-Anker. Vuetify-Strukturklassen, `nth-child` und generierte IDs sind keine dauerhaften Selektoren.
7. **Rollen- und Datenprüfung vor Start:** Route, Rolle, Daten, Viewport und konkurrierende Dialoge werden geprüft, bevor ein Overlay erscheint.
8. **Abschluss und Schließen unterscheiden:** `completed` bedeutet bewusst bis zum Ende geführt. Vorzeitiges Schließen wird separat als `dismissed` gespeichert.
9. **Immer manuell wiederholbar:** Ein zukünftiges Hilfe-/Tour-Center listet passende Touren unabhängig vom Auto-Trigger.
10. **Barrierearm:** Fokus bleibt im Popover, Escape schließt, Zurück/Weiter ist per Tastatur möglich, Texte werden von Screenreadern angekündigt und Bewegungsreduktion wird respektiert.

## 3. First-Time-Onboarding

Ein komplett neuer Benutzer sieht zuerst `onboarding-v1` auf `/`, nachdem Token, Benutzer-ID und Rolle geladen sowie die Modellliste entweder geladen oder als leer bestätigt wurde. Die Login-Seite ist ungeeignet: Sie beschreibt eine technische lokale Token-Beschaffung und liegt vor der verlässlichen Benutzeridentität.

Die Tour umfasst vier Schritte und beantwortet nur:

- Wo befinden sich eigene Modelle?
- Beginne ich frei oder aus einer Aufgabe?
- Wo finde ich Saves und Releases bestehender Modelle?
- Welche Hauptbereiche stehen meiner Rolle zur Verfügung?

Bewusst nicht erklärt werden Sprachdefinition, Syntax, Feedbackkonfiguration, Import/Export, Grid-Einstellungen, Archive, Timeline-Restore und Admin-Aufgabenverwaltung. Diese Informationen sind beim ersten Besuch entweder nicht handlungsrelevant oder zu spezialisiert.

Nach dem Anlegen oder Öffnen eines Modells kann `modeling-basics-v1` kontextuell starten. Bei einem Aufgabenmodell kann anschließend `task-modeling-v1` angeboten werden. Admins erhalten Sprach- und Aufgabentouren erst beim ersten Besuch der jeweiligen Route.

## 4. Empfohlene Product Tours

### 4.1 `onboarding-v1` – Einstieg in „My Models“

**Typ:** Product Tour  
**Priorität:** P0 – jeder Benutzer startet hier; die Wahl zwischen freiem Modell und Aufgabe bestimmt den nächsten Workflow.  
**Zweck:** Orientierung auf der tatsächlichen Startseite und sicherer Einstieg in den ersten Modellierungsfall.  
**Zielgruppe:** alle neuen authentifizierten Benutzer.  
**Startbedingung:** erster erfolgreicher Besuch von `/`, Tourstatus fehlt, `userStore.userId` ist bekannt und `ViewHome` hat das Laden beendet.  
**Voraussetzungen:** gültige Session; keine offenen Dialoge; Desktop-Viewport. Die Tour funktioniert auch bei leerer Modellliste.  

#### Schritt 1 – Persönlicher Modellkatalog

- **Zielelement:** Seitenkopf „My Models“.
- **Erklärt:** Hier liegen eigene freie Modelle und Lösungen zu Aufgaben.
- **Interaktion:** keine.
- **Weiter:** Weiter-Button.
- **Technisches Ziel:** `ViewHome.vue`, Route `/`, bestehender Bereich um `h1.text-h4`; späterer Anker `home-heading` empfohlen.

#### Schritt 2 – Passenden Start wählen

- **Zielelement:** Aktionsgruppe „From task“ und „New Model“.
- **Erklärt:** „New Model“ beginnt frei; „From task“ übernimmt festgelegte Sprachen, Modus und Aufgabentext einer veröffentlichten Aufgabe.
- **Interaktion:** optional einen Button wählen; die Tour muss auch mit „Weiter“ fortsetzbar sein.
- **Weiter:** Benutzeraktion oder Weiter-Button.
- **Technisches Ziel:** `ViewHome.vue`; aktuell kein stabiler gemeinsamer Selektor, später `home-create-actions`.

#### Schritt 3 – Modelle wiederfinden und versionieren

- **Zielelement:** Tabs, Suche und Modelltabelle als gemeinsamer Katalogbereich.
- **Erklärt:** Freie Modelle, Aufgabenmodelle und Archiv sind getrennt. Eine Zeile lässt sich aufklappen, um Releases und alle Saves zu sehen.
- **Interaktion:** keine automatische Zeilenöffnung; bei vorhandenen Daten darf der Benutzer eine Zeile öffnen.
- **Weiter:** Weiter-Button.
- **Technisches Ziel:** `ViewHome.vue`, `v-tabs`, `v-data-table-server`; später `home-model-catalog`.

#### Schritt 4 – Rollenabhängige Navigation

- **Zielelement:** `HeaderMain`.
- **Erklärt:** „Modelle“ ist der Arbeitsbereich für alle. Nur Admins erhalten zusätzlich Erklärtext zu Sprachkatalog, Spracheditor und Tasks.
- **Interaktion:** keine.
- **Weiter:** „Fertig“; optionaler CTA „Erstes Modell öffnen“ nur, wenn ein Modell vorhanden ist.
- **Technisches Ziel:** `HeaderMain.vue`; später `main-navigation`. Nicht erlaubte Links müssen aus dem Schrittinhalt ausgeblendet werden.

**Ende der Tour:** abgeschlossen nach Schritt 4. Vorzeitiges Schließen wird als `dismissed`, nicht als abgeschlossen gespeichert; einmalige erneute Einladung nach einigen Tagen ist für P0 vertretbar. Manuell jederzeit neu startbar.

### 4.2 `modeling-basics-v1` – Erstes Modell bearbeiten

**Typ:** Product Tour  
**Priorität:** P0 – der Modellierungsarbeitsplatz ist die Kernfunktion und Sprachzuordnung plus Drag-and-drop sind ohne Erklärung schwer zu entdecken.  
**Zweck:** Vom geöffneten Modell zum ersten editier- und speicherbaren Modellzustand führen.  
**Zielgruppe:** alle Benutzer beim ersten Modellierungsarbeitsplatz; textlich unterschieden nach freiem und aufgabengebundenem Modell.  
**Startbedingung:** erster vollständig geladener Besuch von `/modeling/:modelId`; kein Recovery-Dialog; Workspace-Sync ist nicht `saving` oder `conflict`.  
**Voraussetzungen:** Modell und Basisversion geladen; Canvas initialisiert. Für freie Modelle darf die Sprachliste leer sein. Für Aufgabenmodelle müssen erforderliche Sprachen aufgelöst sein.

#### Schritt 1 – Modellsprachen festlegen

- **Zielelement:** rechter Tab „Languages“ und `Manage Languages`.
- **Erklärt:** Die Sprache bestimmt verfügbare Elemente, Verbindungen, Regeln und Feedback. Aufgabensprachen sind fest; in freien Modellen werden veröffentlichte Sprach-Releases hier ergänzt.
- **Interaktion:** Bei leerer Sprachliste CTA „Sprache hinzufügen“. Die Tour pausiert, während der Benutzer Dialog, Sprache und Release auswählt, und setzt nach `workspace.editorLanguages.length > 0` fort. Keine automatische Auswahl.
- **Weiter:** bei vorhandener Sprache sofort, sonst nach erfolgreichem Hinzufügen oder bewusstem Überspringen.
- **Technisches Ziel:** `SidebarRightContainer.vue`, `SidebarLibrary.vue`, `useModelWorkspaceStore`; aktuelle Klasse `.library-sidebar`, später `model-languages`.

#### Schritt 2 – Elemente auf die Zeichenfläche ziehen

- **Zielelement:** linker `ElementsSidebar`.
- **Erklärt:** Sprachgruppen sind zunächst eingeklappt. Gruppe öffnen und ein Element per Drag-and-drop auf die Zeichenfläche ziehen; Suche und Ansichten helfen bei großen Sprachen.
- **Interaktion:** Empfohlen ist eine Checklisten-Interaktion außerhalb des Spotlight-Overlays, weil Overlays Drag-and-drop abfangen können. Der Benutzer öffnet eine Gruppe und zieht optional ein Element.
- **Weiter:** Benutzeraktion oder „Überspringen“; nicht vom Erzeugen echter Daten abhängig machen.
- **Technisches Ziel:** `ElementsSidebar.vue`; bestehende Klasse `.elements-sidebar`, später `element-palette` und je Sprachgruppe ein stabiler fachlicher Anker.

#### Schritt 3 – Auf dem Canvas arbeiten

- **Zielelement:** Zeichenfläche.
- **Erklärt:** Auswählen, verschieben, per Doppelklick Beschriftungen bearbeiten und mit Mausrad zoomen. Shortcut-Hilfe liegt unten rechts.
- **Interaktion:** keine erzwungene Modelländerung.
- **Weiter:** Weiter-Button.
- **Technisches Ziel:** `DrawingCanvas.vue`, bestehende Klasse `.graph-container`; später `model-canvas`.

#### Schritt 4 – Verbindungstyp wählen

- **Zielelement:** aktive Verbindung in `ConnectionToolbar`.
- **Erklärt:** Verbindungen werden nach Sprache gruppiert; Palette bietet Suche, zuletzt verwendete und angeheftete Typen.
- **Interaktion:** Palette kontrolliert öffnen; Benutzer darf einen Typ auswählen. Schritt wird übersprungen, wenn keine Verbindung definiert ist.
- **Weiter:** Auswahl oder Weiter-Button; Palette beim Verlassen schließen.
- **Technisches Ziel:** `ConnectionToolbar.vue`, bestehende Klasse `.active-connection`; später `connection-picker`.

#### Schritt 5 – Änderungen sicher speichern

- **Zielelement:** Save-Gruppe im `ModelingHeader`.
- **Erklärt:** Save erstellt einen Checkpoint. Ein Release ist erst nach einem synchronisierten Checkpoint möglich; Statusfarbe zeigt Saved, Unsaved, Offline oder Conflict.
- **Interaktion:** keine automatische Speicherung.
- **Weiter:** Weiter-Button.
- **Technisches Ziel:** `ModelingHeader.vue`, `.modeling-header__save-group`; später `model-save-controls`.

#### Schritt 6 – Werkzeuge bewusst später entdecken

- **Zielelement:** rechte Sidebar-Tabs und Autonomy-Modus.
- **Erklärt:** Feedback, Import/Export, Sprachen und – bei Aufgaben – Task Edits sind kontextuelle Werkzeuge. Der Feedbackmodus bestimmt, wie Regeln reagieren und kann bei Aufgaben gesperrt sein.
- **Interaktion:** keine.
- **Weiter:** „Fertig“; optional „Versionierung erklären“.
- **Technisches Ziel:** `SidebarRightContainer.vue`, `AutonomyControls.vue`; später `model-tool-sidebar` und `autonomy-mode`.

**Ende der Tour:** abgeschlossen nach Schritt 6, unabhängig davon, ob ein Element erzeugt wurde. Vorzeitiges Schließen ist `dismissed`; P0 darf einmal erneut angeboten werden. Manuell neu startbar. Eine tatsächlich hinzugefügte Sprache oder Modelländerung ist ein separates Produkt-Ereignis, kein Ersatz für den Tourabschluss.

### 4.3 `task-modeling-v1` – Mit einer Aufgabe modellieren

**Typ:** Product Tour  
**Priorität:** P1 – sehr hilfreich für aufgabengebundene Modelle, aber nicht jeder Benutzer arbeitet mit Aufgaben.  
**Zweck:** Aufgabentext, Referenzen, gesperrte Vorgaben und persönliche Task Edits verständlich machen.  
**Zielgruppe:** Benutzer eines Modells mit `workspace.taskReference`.  
**Startbedingung:** erster geladener Aufgaben-Workspace; `taskVersion` und Task-Text sind vorhanden; `modeling-basics-v1` ist abgeschlossen oder wurde verworfen.  
**Voraussetzungen:** `/modeling/:modelId`, Aufgabenleiste im DOM, kein Recovery- oder Sample-Dialog.

#### Schritt 1 – Aufgabe im Workspace

- **Zielelement:** `TaskTopBar`.
- **Erklärt:** Der Aufgabentext gehört zu einer festen Aufgabenversion und kann ein- und ausgeklappt oder als schwebendes Fenster geöffnet werden.
- **Interaktion:** Ein-/Ausklappen zulassen; Ausgangszustand nach dem Schritt wiederherstellen.
- **Weiter:** Weiter-Button.
- **Technisches Ziel:** `TaskTopBar.vue`, `.task-topbar`; später `task-topbar`.

#### Schritt 2 – Verweise direkt verwenden

- **Zielelement:** referenzierter Element- oder Verbindungstext im Task-Editor.
- **Erklärt:** Elementreferenzen lassen sich auf das Canvas ziehen; Verbindungsreferenzen wählen den passenden Verbindungstyp.
- **Interaktion:** nur wenn mindestens eine Referenz existiert; ansonsten Schritt überspringen. Kein automatisches Drag-and-drop.
- **Weiter:** Benutzeraktion oder Weiter.
- **Technisches Ziel:** `TaskEditEditor.vue` und `taskEditorExtensions.ts`; Referenz-Markup ist datenabhängig, später `task-reference` plus fachliche Referenz-ID.

#### Schritt 3 – Aufgabe persönlich annotieren

- **Zielelement:** Edit-Mode-Button in `TaskTopBar`.
- **Erklärt:** Formatierungen oder eigener Zusatztext werden als persönliche Task Edits gespeichert, ohne den Originaltext der Aufgabe zu verändern.
- **Interaktion:** Edit-Modus kontrolliert einschalten; keine Textmutation erzwingen.
- **Weiter:** Weiter-Button.
- **Technisches Ziel:** `TaskTopBar.vue`, `TaskEditEditor.vue`; später `task-edit-mode`.

#### Schritt 4 – Task Edits verwalten

- **Zielelement:** rechter Task-Tab und `TaskEditsSidebar`.
- **Erklärt:** Edits lassen sich filtern, im Text fokussieren, entfernen und über die Snackbar rückgängig machen; Sync-Status ist getrennt vom Modell-Checkpoint.
- **Interaktion:** Tab öffnen, aber nichts entfernen.
- **Weiter:** Weiter-Button; vorherigen Sidebar-Tab danach wiederherstellen.
- **Technisches Ziel:** `SidebarRightContainer.vue`, `TaskEditsSidebar.vue`; später `task-edits-sidebar`.

#### Schritt 5 – Feste Vorgaben und Musterlösungen

- **Zielelement:** gesperrter `AutonomyControls`-Button; optional zusätzlich „Sample solutions“.
- **Erklärt:** Sprache und Modus stammen aus der Aufgabe. Musterlösungen sind nur verfügbar, wenn der Autor veröffentlichte Modellversionen hinterlegt hat.
- **Interaktion:** keine; Sample-Teil bei fehlenden Lösungen ausblenden.
- **Weiter:** „Fertig“.
- **Technisches Ziel:** `ViewModeling.vue`, `AutonomyControls.vue`; später `task-mode` und `sample-solutions`.

**Ende der Tour:** abgeschlossen nach Schritt 5. Schließen gilt als `dismissed`, nicht als abgeschlossen; kein automatischer erneuter Start, aber manuell wiederholbar.

### 4.4 `model-versioning-v1` – Checkpoints, Releases und Timeline

**Typ:** Product Tour  
**Priorität:** P1 – Versionierung ist zentral, aber erst nach ersten Modelländerungen sinnvoll.  
**Zweck:** Unterschied zwischen Checkpoint und Release sowie sichere Restore-/Branch-Möglichkeiten erklären.  
**Zielgruppe:** alle Modellierenden mit einem gespeicherten Modell.  
**Startbedingung:** Benutzer hat erstmals einen Checkpoint gespeichert oder öffnet die Timeline erstmals; kein Sync-Konflikt.  
**Voraussetzungen:** `/modeling/:modelId`, `workspace.model` und `baseVersionId` vorhanden.

#### Schritt 1 – Checkpoint und Status

- **Zielelement:** Save-Button und Statusfarbe.
- **Erklärt:** Checkpoints sichern den Arbeitsstand; Offline- und Konfliktzustände werden sichtbar, lokale Drafts sind nur Recovery und keine reguläre Version.
- **Interaktion:** keine Speicherung auslösen.
- **Weiter:** Weiter.
- **Technisches Ziel:** `ModelingHeader.vue`, `.modeling-header__save-group`.

#### Schritt 2 – Release als benannter Meilenstein

- **Zielelement:** Release-Button.
- **Erklärt:** Releases sind benannte, vollständige Stände. Der Button bleibt deaktiviert, solange lokale Änderungen oder Patches nicht als Checkpoint synchronisiert sind.
- **Interaktion:** keinen Release-Dialog automatisch bestätigen; optional Dialog nur öffnen und wieder schließen.
- **Weiter:** Weiter.
- **Technisches Ziel:** `ModelingHeader.vue`; später `model-release`.

#### Schritt 3 – Timeline lesen

- **Zielelement:** Timeline-Button, danach Timeline-Slider.
- **Erklärt:** Releases und Checkpoint-Patches bilden eine Zeitleiste; orange markiert lokale, noch nicht gespeicherte Änderungen.
- **Interaktion:** Timeline kontrolliert öffnen und vorhandene Positionen nur als Vorschau wechseln.
- **Weiter:** Weiter.
- **Technisches Ziel:** `ModelTimelineDialog.vue`, Teleport-Dialog; später `model-timeline` und `model-timeline-slider`.

#### Schritt 4 – Restore oder Branch

- **Zielelement:** Dialogaktionen „Restore as checkpoint“ und „Branch from here“.
- **Erklärt:** Restore setzt einen früheren Stand als neuen Checkpoint fort; Branch erstellt ein neues Modell. Task Edits werden nur auf ausdrückliche Wahl übernommen.
- **Interaktion:** keine Aktion ausführen.
- **Weiter:** „Fertig“; Tour schließt den nur für die Tour geöffneten Dialog.
- **Technisches Ziel:** `ModelTimelineDialog.vue`.

**Ende der Tour:** abgeschlossen nach Schritt 4. Vorzeitiges Schließen ist `dismissed`. Kein automatischer Neustart; manuell wiederholbar.

### 4.5 `language-catalog-v1` – Sprachkatalog verwalten

**Typ:** Product Tour  
**Priorität:** P1 – essentiell für Admins, aber für normale Modellierende irrelevant.  
**Zweck:** Lebenszyklus einer Sprache vom Anlegen über Testen bis zum Fork erklären.  
**Zielgruppe:** Administratoren.  
**Startbedingung:** erster Besuch von `/diagramLanguages` nach geladenem Katalog.  
**Voraussetzungen:** `globalRole === 'ADMIN'`, keine offene Sprachdialogbox.

#### Schritt 1 – Sprache anlegen

- **Zielelement:** „New Language“.
- **Erklärt:** Eine neue Sprache erhält automatisch ein erstes Release; optional kann eine vorhandene Version als Parent dienen.
- **Interaktion:** Dialog darf geöffnet, aber nicht automatisch abgesendet werden.
- **Weiter:** Weiter oder Dialog schließen.
- **Technisches Ziel:** `ViewDiagramLanguageOverview.vue`, `DialogLanguageEditor.vue`; später `language-create`.

#### Schritt 2 – Öffnen und direkt testen

- **Zielelement:** Aktionsbereich einer vorhandenen Tabellenzeile.
- **Erklärt:** „Open“ bearbeitet die Definition. „Try“ startet einen temporären neuen Modell-Workspace mit dieser Sprachversion.
- **Interaktion:** keine Navigation während der Tour.
- **Weiter:** Weiter; bei leerem Katalog mit erklärendem Leerzustand überspringen.
- **Technisches Ziel:** `ViewDiagramLanguageOverview.vue`; später pro Zeile `language-actions` mit Sprach-ID.

#### Schritt 3 – Releases und alle Saves

- **Zielelement:** aufgeklappter Zeilenbereich mit Tabs „Releases“ und „All Saves“.
- **Erklärt:** Releases sind freigegebene Meilensteine; Checkpoints bleiben unter allen Saves verfügbar.
- **Interaktion:** erste Zeile kontrolliert aufklappen, falls vorhanden; UI-Zustand danach wiederherstellen.
- **Weiter:** Weiter.
- **Technisches Ziel:** `LanguageVersionList.vue`; später `language-version-history`.

#### Schritt 4 – Frühere Version weiterverwenden

- **Zielelement:** „Use as new language“ und „Open“ einer Version.
- **Erklärt:** Eine alte Version kann geöffnet/wiederhergestellt oder als eigenständige neue Sprache geforkt werden, ohne die Historie zu überschreiben.
- **Interaktion:** keine Mutation.
- **Weiter:** „Fertig“.
- **Technisches Ziel:** `ViewDiagramLanguageOverview.vue`, `LanguageVersionList.vue`.

**Ende der Tour:** abgeschlossen nach Schritt 4. Schließen ist `dismissed`; manuell wiederholbar.

### 4.6 `language-authoring-v1` – Sprache grundlegend bearbeiten

**Typ:** Product Tour  
**Priorität:** P1 – der Drei-Spalten-Editor und seine Versionierung sind für Admins zentral und nicht selbsterklärend.  
**Zweck:** Arbeitsmuster „auswählen – konfigurieren – prüfen – speichern“ vermitteln.  
**Zielgruppe:** Administratoren, die erstmals eine konkrete Sprache öffnen.  
**Startbedingung:** erster vollständig geladener Besuch von `/diagramLanguageEditor/:id`.  
**Voraussetzungen:** Admin, `store.language` und `store.currentVersion` geladen, kein Unsaved-Changes-Dialog.

#### Schritt 1 – Status und Versionsaktionen

- **Zielelement:** Editor-Toolbar.
- **Erklärt:** Dirty-Status, Checkpoint, Release und History betreffen die gesamte Sprachdefinition über alle Tabs.
- **Interaktion:** keine Speicherung.
- **Weiter:** Weiter.
- **Technisches Ziel:** `ViewDiagramLanguageEditor.vue`, `.editor-toolbar`; später `language-editor-toolbar`.

#### Schritt 2 – Fachbereiche der Sprache

- **Zielelement:** Editor-Tabs.
- **Erklärt:** Elemente und Verbindungen bilden die Notation; Syntax legt Regeln fest; Feedback konfiguriert Rückmeldungen. Settings ist derzeit deaktiviert und wird nicht als Arbeitsweg beworben.
- **Interaktion:** keine automatische Tabfolge.
- **Weiter:** Weiter.
- **Technisches Ziel:** `ViewDiagramLanguageEditor.vue`, `.editor-tabs`; später `language-editor-tabs`.

#### Schritt 3 – Definition auswählen oder anlegen

- **Zielelement:** linke Entitätsliste im aktiven Elements-Tab.
- **Erklärt:** Neue Definitionen entstehen hier; Löschen ist eine echte Änderung an der aktuellen Arbeitsversion.
- **Interaktion:** keine Entität automatisch anlegen oder löschen.
- **Weiter:** Weiter.
- **Technisches Ziel:** `EditorEntityList.vue` in `ElementEditor.vue`; später `language-entity-list`.

#### Schritt 4 – Eigenschaften schrittweise konfigurieren

- **Zielelement:** mittleres Eigenschaftenformular.
- **Erklärt:** Basisfelder sind direkt sichtbar; Style, Editing, Connection Points, Layout, Collapse und Child Elements liegen in Expansion Panels.
- **Interaktion:** ein ungefährliches Panel darf kontrolliert geöffnet werden.
- **Weiter:** Weiter.
- **Technisches Ziel:** `ElementPropertiesEditor.vue`; später `language-entity-form`.

#### Schritt 5 – Live-Vorschau statt Blindflug

- **Zielelement:** rechte Preview-Karte.
- **Erklärt:** Die Vorschau verwendet denselben Canvas-Stack wie der Modellierungsarbeitsplatz und dient zum Testen von Elementen, Verbindungen und Regeln vor dem Release.
- **Interaktion:** keine.
- **Weiter:** „Fertig“; CTA zu Syntax- oder Feedback-Tour nur, wenn deren Voraussetzungen erfüllt sind.
- **Technisches Ziel:** `ElementEditor.vue`, `.preview-card`; später `language-preview`.

**Ende der Tour:** abgeschlossen nach Schritt 5. Schließen ist `dismissed`; manuell wiederholbar.

### 4.7 `language-syntax-v1` – Syntax und Kardinalitäten definieren

**Typ:** Product Tour  
**Priorität:** P2 – mächtig und schwer zu entdecken, aber nur für fortgeschrittene Sprachautoren relevant.  
**Zweck:** Matrix, Regelverfeinerung und Feedbackmodus in der Vorschau erklären.  
**Zielgruppe:** Administratoren mit mindestens einer Sprache, die Elemente enthält.  
**Startbedingung:** erster bewusster Wechsel auf den Tab `Syntax`, nicht automatisch beim Öffnen des Editors.  
**Voraussetzungen:** `/diagramLanguageEditor/:id`, mindestens ein Element; für Verbindungs- und Kardinalitätsdetails mindestens ein Verbindungstyp.

#### Schritt 1 – Verbindungsmatrix

- **Zielelement:** Matrix in `MultiplicityForm`.
- **Erklärt:** Jede Zelle wechselt zwischen undefiniert, erlaubt und verboten und beschreibt eine gerichtete Kombination von Quell- und Zielelement.
- **Interaktion:** keine Zelle automatisch verändern.
- **Weiter:** Weiter.
- **Technisches Ziel:** `SyntaxEditor.vue`, `MultiplicityForm.vue`; später `syntax-matrix`.

#### Schritt 2 – Regel verfeinern

- **Zielelement:** Detail-/Refinement-Bereich der gewählten Relation.
- **Erklärt:** Erlaubte Beziehungen lassen sich auf konkrete Verbindungstypen und Kardinalitäten einschränken.
- **Interaktion:** nur wenn eine passende Relation existiert; andernfalls informativ überspringen.
- **Weiter:** Weiter.
- **Technisches Ziel:** `MultiplicityForm.vue`; später `syntax-refinement`.

#### Schritt 3 – Meldung und Reaktionsmodus

- **Zielelement:** Message-Template beziehungsweise Regeltext und Autonomy-Modus der Vorschau.
- **Erklärt:** Die Sprache liefert die fachliche Meldung; der Modus bestimmt, ob Regelverletzungen frei, hinweisend oder präventiv behandelt werden.
- **Interaktion:** Modus in der Vorschau darf temporär gewechselt und danach wiederhergestellt werden.
- **Weiter:** Weiter.
- **Technisches Ziel:** `SyntaxEditorForm.vue`, `AutonomyControls.vue`.

#### Schritt 4 – Regel im Preview testen

- **Zielelement:** Syntax-Preview.
- **Erklärt:** Regeln sollten mit realen Element- und Verbindungskombinationen geprüft werden, bevor ein Release entsteht.
- **Interaktion:** keine erzwungene Graphänderung.
- **Weiter:** „Fertig“.
- **Technisches Ziel:** `SyntaxEditor.vue`, `.preview-canvas`.

**Ende der Tour:** abgeschlossen nach Schritt 4. Schließen gilt als gesehen und `dismissed`, da P2 nicht erneut automatisch erscheinen soll. Manuell wiederholbar.

### 4.8 `language-feedback-v1` – Feedback konfigurieren

**Typ:** Product Tour  
**Priorität:** P2 – hochkomplex, aber erst nach stabiler Notation und Syntax sinnvoll.  
**Zweck:** Unterschied zwischen Overlays und eigenen Feedback-Elementen erklären.  
**Zielgruppe:** Administratoren, die Feedback für eine Sprache konfigurieren.  
**Startbedingung:** erster bewusster Wechsel auf `Feedback`.  
**Voraussetzungen:** konkrete Sprache geladen; für Overlay-Tour mindestens ein Element oder eine Verbindung.

#### Schritt 1 – Zwei Arten von Feedback

- **Zielelement:** Tabs `Overlay` und `Feedback Elements`.
- **Erklärt:** Overlays markieren vorhandene Modellobjekte; Feedback Elements sind eigene Objekte auf einer separaten Feedback-Ebene.
- **Interaktion:** keine.
- **Weiter:** Weiter.
- **Technisches Ziel:** `FeedbackEditor.vue`; später `feedback-kind-tabs`.

#### Schritt 2 – Ziel auswählen

- **Zielelement:** linke Liste „Feedback Targets“.
- **Erklärt:** Overlay-Konfiguration ist pro Element- oder Verbindungstyp gespeichert.
- **Interaktion:** ein vorhandenes Ziel darf ausgewählt werden; ohne Ziel Schritt überspringen.
- **Weiter:** Auswahl oder Weiter.
- **Technisches Ziel:** `FeedbackEditor.vue`, `EditorEntityList.vue`; später `feedback-target-list`.

#### Schritt 3 – Zustände konfigurieren

- **Zielelement:** mittleres Overlay-Formular.
- **Erklärt:** Icon, Größe, Ausrichtung beziehungsweise Offset, Tooltip und Cursor werden pro Feedbackzustand konfiguriert.
- **Interaktion:** Expansion Panel darf geöffnet werden; keine Werte ändern.
- **Weiter:** Weiter.
- **Technisches Ziel:** `FeedbackEditorForm.vue`; später `feedback-overlay-form`.

#### Schritt 4 – Eigene Feedback-Elemente und Regeln

- **Zielelement:** Tab `Feedback Elements` und dessen Untertabs.
- **Erklärt:** Feedback-Element, dedizierte Verbindung und Regeln steuern, was Quelle oder Ziel sein darf und ob Elemente auf der Feedback-Ebene gesperrt bleiben.
- **Interaktion:** Tab kontrolliert wechseln; Ausgangszustand am Ende wiederherstellen.
- **Weiter:** Weiter.
- **Technisches Ziel:** `FeedbackCanvasConfiguratorForm.vue`; später `feedback-canvas-config`.

#### Schritt 5 – Zustände im Preview prüfen

- **Zielelement:** Feedback Preview und State-Toggle.
- **Erklärt:** Zustände lassen sich im selben Canvas-Kontext prüfen, bevor die Sprachversion gespeichert oder veröffentlicht wird.
- **Interaktion:** Vorschauzustand temporär umschalten.
- **Weiter:** „Fertig“.
- **Technisches Ziel:** `FeedbackEditor.vue`, `.preview-card`; später `feedback-preview`.

**Ende der Tour:** abgeschlossen nach Schritt 5. Schließen gilt als `dismissed` und verhindert weitere Auto-Starts. Manuell wiederholbar.

### 4.9 `task-authoring-v1` – Aufgabe erstellen und veröffentlichen

**Typ:** Product Tour  
**Priorität:** P1 – Kernworkflow für Admins, mit mehreren voneinander abhängigen Einstellungen.  
**Zweck:** Aufgabe von der Identität bis zum nutzbaren Release konfigurieren.  
**Zielgruppe:** Administratoren.  
**Startbedingung:** erster Besuch von `/tasks` nach geladenen Katalogen; idealerweise nachdem eine Aufgabe gewählt oder neu angelegt wurde.  
**Voraussetzungen:** Admin; Sprach- und Modellkatalog-Ladevorgänge beendet. Schritte 2–6 setzen eine ausgewählte Aufgabe voraus und werden sonst erst nach der Auswahl fortgesetzt.

#### Schritt 1 – Aufgaben finden und Besitz verstehen

- **Zielelement:** linke Task-Sidebar mit Suche, `My Tasks`, `All Tasks` und `Archive`.
- **Erklärt:** Aufgaben sind geteilt und versioniert; farbige Punkte zeigen eigene und fremde Aufgaben, Sichtbarkeit zeigt privat oder veröffentlicht.
- **Interaktion:** optional Aufgabe wählen oder „New task“ nutzen; keine automatische Erstellung.
- **Weiter:** nach Auswahl oder Weiter.
- **Technisches Ziel:** `ViewTaskEditor.vue`, `.task-sidebar`; später `task-catalog`.

#### Schritt 2 – Metadaten, Branch und Sichtbarkeit

- **Zielelement:** Titelzeile des Task-Editors.
- **Erklärt:** Name wird beim Verlassen gespeichert; Branch erzeugt eine neue Aufgabe; Globus/Schloss veröffentlicht oder privatisiert; Archiv ist davon getrennt.
- **Interaktion:** keine Sichtbarkeit ändern.
- **Weiter:** Weiter.
- **Technisches Ziel:** `ViewTaskEditor.vue`, `.task-editor > .v-card-title`; später `task-metadata`.

#### Schritt 3 – Feste Sprach-Releases wählen

- **Zielelement:** `Workspace languages`.
- **Erklärt:** Nur konkrete Sprach-Releases werden eingebunden. Diese sind im späteren Aufgabenmodell erforderlich und nicht austauschbar.
- **Interaktion:** keine automatische Auswahl.
- **Weiter:** Weiter.
- **Technisches Ziel:** `ViewTaskEditor.vue`; vorhandene Label-ID `task-workspace-languages-label`, später Anker auf dem gesamten Feld.

#### Schritt 4 – Modellierungsverhalten und Musterlösungen

- **Zielelement:** `Modeling behavior` und `Sample solution releases`.
- **Erklärt:** Der Modus wird für Lernende gesperrt. Nur veröffentlichte Modell-Releases eignen sich als Musterlösungen.
- **Interaktion:** keine Werte ändern.
- **Weiter:** Weiter.
- **Technisches Ziel:** vorhandene IDs `task-modeling-behavior-label`, `task-sample-solutions-label`; `AutonomyControls.vue`.

#### Schritt 5 – Aufgabentext mit Modellbezug

- **Zielelement:** `TaskRichEditor` und Link-Menü.
- **Erklärt:** Der Text unterstützt Formatierung und semantische Referenzen auf Elemente und Verbindungen der ausgewählten Sprachen. Diese Referenzen werden im Aufgabenmodell interaktiv.
- **Interaktion:** Link-Menü nur öffnen, wenn Optionen vorhanden sind; nichts einfügen.
- **Weiter:** Weiter.
- **Technisches Ziel:** `TaskRichEditor.vue`; später `task-content-editor` und `task-reference-menu`.

#### Schritt 6 – Checkpoint, Release, Publish

- **Zielelement:** Versionsauswahl sowie Buttons „Save checkpoint“ und „Create release“.
- **Erklärt:** Checkpoint speichert Arbeitsstände; Release ist der konsumierbare Meilenstein. Veröffentlichung der Aufgabe und Release-Erstellung sind zwei getrennte Zustände, beide müssen stimmen, damit normale Benutzer die Aufgabe wählen können.
- **Interaktion:** keine Speicherung oder Veröffentlichung auslösen.
- **Weiter:** „Fertig“.
- **Technisches Ziel:** `ViewTaskEditor.vue`, `.version-select` und Aktionsgruppe; später `task-version-actions`.

**Ende der Tour:** abgeschlossen nach Schritt 6. Vorzeitiges Schließen ist `dismissed`; manuell wiederholbar.

## 5. Feature Hints statt vollständiger Touren

### `hint-connection-favorites-v1` – Angeheftete und letzte Verbindungen

- **Typ:** Feature Hint, P2.
- **Zielgruppe/Trigger:** Modellierende beim zweiten Öffnen der Verbindungspalette, wenn mindestens mehrere Verbindungstypen existieren.
- **Ziel:** Pin-Icon eines Verbindungseintrags.
- **Text:** Häufige Typen können angeheftet werden; kürzlich verwendete erscheinen automatisch unter „Recent“.
- **Warum Hint:** Eine einzelne, lokale Aktion; der restliche Verbindungsworkflow ist bereits bekannt.
- **Technik:** `ConnectionToolbar.vue`; Status ist bereits pro Modell in `Model.preferences.connectionToolbar` gespeichert.
- **Ende:** Schließen zählt als gesehen; manuell nicht zwingend als eigene Tour, aber im Hilfecenter dokumentierbar.

### `hint-model-import-export-v1` – XML Import/Export

- **Typ:** Feature Hint, P2.
- **Zielgruppe/Trigger:** erster manueller Wechsel auf den rechten Tab „Import/Export“.
- **Ziel:** Buttons Download und Upload.
- **Text:** Download exportiert natives maxGraph-XML; Upload ersetzt den Inhalt des aktuellen Canvas und sollte bewusst verwendet werden.
- **Warum Hint:** Nur zwei lokale Aktionen; eine geführte Upload-Tour würde Dateiauswahl und potenziell destruktive Datenänderung verlangen.
- **Technik:** `SidebarPersistence.vue`.
- **Ende:** Schließen zählt als gesehen.

### `hint-sample-solutions-v1` – Musterlösungen

- **Typ:** Feature Hint, P2.
- **Zielgruppe/Trigger:** erstes Aufgabenmodell, dessen Aufgabenversion mindestens eine Musterlösung enthält.
- **Ziel:** Button „Sample solutions“.
- **Text:** Öffnet eine schreibgeschützte Vorschau veröffentlichter Musterlösungen; das eigene Modell wird nicht verändert.
- **Warum Hint:** Ein einzelner bedingter Button mit selbsterklärendem Dialog.
- **Technik:** `ViewModeling.vue`, `ModelSnapshotPreview.vue`.
- **Ende:** Öffnen oder Schließen zählt als gesehen.

### `hint-connection-settings-level-v1` – Basic, Advanced, Expert

- **Typ:** Feature Hint, P2.
- **Zielgruppe/Trigger:** Admin öffnet erstmals eine Verbindung im Spracheditor.
- **Ziel:** Settings-Level-Toggle.
- **Text:** Basic zeigt häufige Optionen; Advanced und Expert blenden zusätzliche Interaktions-, Port- und Routingfelder ein, ohne separate Verbindungsvarianten zu erzeugen.
- **Warum Hint:** Das Feature sitzt in einem einzigen Formular und benötigt keine Sequenz.
- **Technik:** `ConnectionEditorForm.vue`.
- **Ende:** Moduswechsel oder Schließen zählt als gesehen.

## 6. Bereiche, die bewusst keine automatische Tour erhalten

- **Login/Token-Beschaffung:** technisch und installationsspezifisch; die vorhandene Expansion erklärt den lokalen Weg. Eine Tour würde vor stabiler Benutzeridentität laufen.
- **Recovery-Dialog:** zeitkritische Entscheidung über lokale, ungespeicherte Arbeit. Ein zusätzlicher Overlay-Layer erhöht das Fehlerrisiko.
- **XML-Upload:** benötigt eine lokale Datei und kann den Canvas ersetzen; nur Hint und Dokumentation.
- **Archivieren, Restore und Branch tatsächlich ausführen:** mutierende Aktionen werden erklärt, aber nie durch eine Tour ausgeführt.
- **Sync-Sidebar:** `SidebarSync.vue` schaltet derzeit nur einen lokalen Connected-State; Event-Log und echte Synchronisation sind nicht implementiert. Eine Tour würde einen unfertigen Produktwert suggerieren.
- **Global Settings:** der Tab zeigt ausdrücklich, dass die Funktion deaktiviert ist.
- **Alle Toolbar-Icons:** Auswahl, Löschen, Duplizieren, Ausrichten, Zoom und Grid besitzen bekannte Icons beziehungsweise Tooltips; eine Tour wäre UI-Inventur ohne ausreichenden Nutzen.
- **Einzelne maxGraph-Zellen:** dynamische SVG-/DOM-Struktur, nutzergenerierte Daten und Zoom machen sie zu instabilen Spotlight-Zielen.
- **Komplette Detailformulare:** Element-, Verbindung-, Syntax- und Feedbackformulare sind zu umfangreich. Kontext-Hints und fachliche Dokumentation sind geeigneter.
- **Mobile Modellierung:** aktuelles Layout ist nicht hinreichend responsiv für zuverlässige angeheftete Touren.

## 7. Technisches Zielbild für eine spätere Umsetzung

### 7.1 Deklaratives Tour-Register

Library-unabhängig sollte jede Tour als Datenstruktur registriert werden, etwa mit:

```text
id
type: tour | hint
priority
audience / roles
route matcher
auto-trigger
prerequisites
steps[]
completion policy
```

Ein zentraler Tour-Manager kann später in der Nähe von `App.vue` eingebunden werden. Er reagiert auf Router-Navigation, Auth-/Rollenbereitschaft und explizite fachliche Ereignisse. Die konkrete Overlay-Library bleibt ein Adapter hinter einer kleinen Schnittstelle wie `start`, `next`, `close`, `destroy` und `refreshTarget`.

Tourtexte und Bedingungen gehören nicht in die Fachkomponenten. Komponenten stellen lediglich semantische Ziele und gegebenenfalls kontrollierte UI-Aktionen bereit, beispielsweise „öffne Timeline“, „wechsle Sidebar-Tab“ oder „ist geladen“.

### 7.2 Selektorstrategie

Aktuell verwendbare, aber nur mittelfristig stabile Ziele sind beispielsweise:

| UI-Bereich | Bestehendes Ziel | Bewertung |
| --- | --- | --- |
| Modellierungsheader | `.modeling-header` | verständlich, aber CSS-gekoppelt |
| Save-Gruppe | `.modeling-header__save-group` | relativ stabil, aber CSS-gekoppelt |
| Canvas | `.graph-container` | fachlich passend, aber mehrfach in Previews vorhanden |
| Elementpalette | `.elements-sidebar` | mehrfach in Editor-Previews möglich |
| Verbindungspalette | `.active-connection` | nur bei vorhandenen Verbindungen |
| Task-Leiste | `.task-topbar` | nur bei Aufgabenmodellen |
| Sprach-Editor-Toolbar | `.editor-toolbar` | nicht global eindeutig |
| Task-Feldlabels | `#task-workspace-languages-label` etc. | stabiler Textbezug, Ziel ist aber nur das Label |

Für die Implementierung werden dedizierte, semantische Anker empfohlen, zum Beispiel `data-tour="model-save-controls"`. Das ist eine spätere Änderung und ausdrücklich nicht Teil dieses Konzeptschritts. Ein Anker benennt die Funktion, nicht Layoutposition oder Text. Wiederholte Entitäten benötigen eine fachliche ID im Selektor oder einen Resolver statt `nth-child`.

Der Resolver sollte Ziele innerhalb einer konkreten View oder Komponenteninstanz suchen. Sonst kann beispielsweise `.graph-container` versehentlich die Preview im Spracheditor statt den Hauptcanvas treffen.

### 7.3 Trigger und fachliche Ereignisse

Route-Besuch allein reicht nicht. Sinnvolle spätere Signale sind:

- `home.modelsLoaded`
- `workspace.loaded`
- `workspace.languagesResolved`
- `workspace.firstCheckpointSaved`
- `task.loaded`
- `language.loaded`
- `catalog.loaded`
- `dialog.closed`

Diese Signale müssen keine globale Event-Bus-Architektur erzwingen. Ein Tour-Manager kann auch auf Pinia-Zustand und explizite Promises warten. Wichtig ist ein eindeutiger Ready-Zustand mit Timeout und Abbruch.

### 7.4 UI-Zustand vorbereiten und bereinigen

Ein Tour-Schritt kann optional `prepare` und `cleanup` besitzen:

- `prepare`: richtigen Tab wählen, ein nicht mutierendes Menü öffnen, auf `nextTick` und ein Zielelement warten.
- `cleanup`: nur Zustände zurücksetzen, die die Tour selbst verändert hat.

Vor dem Start wird ein Snapshot relevanter UI-Zustände gehalten: aktiver Tab, Sidebar-Tab, geöffnete Palette oder Timeline. Fachzustand wie Sprache, Modell, Sichtbarkeit oder Formulardaten wird nie automatisch verändert.

## 8. Tour-IDs und Versionierung

Empfohlenes Schema:

```text
onboarding-v1
modeling-basics-v1
task-modeling-v1
model-versioning-v1
language-catalog-v1
language-authoring-v1
language-syntax-v1
language-feedback-v1
task-authoring-v1
hint-connection-favorites-v1
```

Die ID beschreibt Inhalt und eigene Inhaltsversion. `-v2` wird nur vergeben, wenn Ziel, Reihenfolge oder Aussage so wesentlich geändert wurden, dass Benutzer die Erklärung erneut sehen sollten. Reine Textkorrekturen benötigen keine neue ID.

Einzelne IDs sind besser als eine globale App-Version, weil:

- eine neue Verbindungspalette nicht das First-Time-Onboarding erneut auslösen soll,
- Rollen unterschiedliche Tourmengen besitzen,
- ein Benutzer einzelne Features bereits kennen kann,
- Touren unabhängig veröffentlicht, zurückgezogen und ausgewertet werden können,
- A/B-Varianten oder Migrationen pro Tour möglich sind,
- der Status bei kleinen Releases stabil bleibt.

Feature-Hints sollten ebenfalls eigene versionierte IDs besitzen. Release-Version und Tour-ID können als Metadaten verknüpft werden, dürfen aber nicht identisch sein.

## 9. Speicherung des Tour-Status

### 9.1 Bewertung der Optionen

| Option | Vorteil | Nachteil im konkreten Projekt |
| --- | --- | --- |
| `localStorage` | sofort verfügbar, offlinefähig, keine Backend-Änderung | geräte- und browsergebunden; muss nach Benutzer-ID getrennt werden; kann gelöscht werden |
| bestehender `userStore` | Rolle und Benutzer-ID liegen bereits vor | nur Arbeitsspeicher; `reset` verliert alles; kein persistenter Preference-Bereich |
| `Model.preferences` | Backend-Persistenz existiert bereits | gehört zu einem einzelnen Modell; würde globale Tourzustände duplizieren und ist auf `/` noch nicht passend |
| Backend/User Preferences | geräteübergreifend und benutzerbezogen | derzeit kein Benutzerprofil-/Preferences-Endpunkt oder entsprechende Collection vorhanden |
| Client + Backend | schneller Start, offlinefähig und geräteübergreifend | benötigt Konflikt- und Merge-Regeln |

### 9.2 Empfehlung

Langfristig wird eine Kombination empfohlen:

1. Backend als maßgebliche Quelle für benutzerbezogene Tourzustände,
2. `localStorage` als schneller, benutzergebundener Cache und Offline-Fallback,
3. `userStore` nur als Laufzeit-Zugriff auf Benutzer-ID, Rolle und geladene Preferences.

Da das Backend aktuell nur Token-Claims zurückgibt, wäre dafür später eine kleine User-Preferences-Ressource erforderlich. Tourstatus gehört nicht in das JWT: Token sind extern ausgestellt, zeitlich begrenzt und für häufige Preference-Updates ungeeignet.

Ein möglicher Status pro Tour:

```text
tourId
state: completed | dismissed | snoozed
lastStep
firstSeenAt
updatedAt
completedAt
```

Für den lokalen Schlüssel ist eine Benutzer-Namensraumtrennung notwendig, beispielsweise sinngemäß `modeling-copilot:tours:<userId>`. Niemals nur einen globalen `onboardingDone`-Schlüssel verwenden, weil mehrere Personen denselben Browser nutzen können.

Merge-Regel: Neuester `updatedAt` gewinnt pro Tour-ID; `completed` darf nicht durch einen älteren lokalen `dismissed`-Status zurückgestuft werden. Ein unbekannter Benutzer darf Status lesen, aber erst nach ermittelter Benutzer-ID automatisch starten. Beim echten Logout sollte Tour-Laufzeitstate zurückgesetzt werden; der persistente Benutzerstatus bleibt erhalten.

Für eine erste Implementierungsphase ohne Backend-Erweiterung ist `localStorage` akzeptabel, wenn der Schlüssel Benutzer-ID und Tour-ID enthält. Der `userStore` allein ist ausdrücklich nicht ausreichend.

## 10. Routing, asynchrone UI und technische Risiken

### 10.1 Router und Lazy Loading

- Auf `router.afterEach` allein kann kein Schritt starten: Die lazy geladene View und deren API-Daten sind dann möglicherweise noch nicht bereit.
- Reihenfolge: Navigation erfolgreich, `nextTick`, fachlichen Ready-Zustand abwarten, Ziel auflösen, dann Tour starten.
- Jeder Wartevorgang benötigt Timeout und Abbruch bei neuer Navigation.
- Da Hash-History verwendet wird, sollte Matching über `route.name` und Params statt `window.location.pathname` erfolgen.
- Eine laufende Tour wird vor jedem Routenwechsel sauber zerstört. Die nächste route-lokale Tour startet separat.

### 10.2 Asynchrone Daten

- Home, Sprachkatalog, Aufgabenliste und Versionen besitzen Ladephasen.
- Modell-Workspace lädt Modellversion, Sprachen, Aufgabe und gegebenenfalls Recovery-Draft.
- Ein sichtbares Zielelement kann existieren, während seine Daten noch leer sind. Voraussetzung ist deshalb fachliche Bereitschaft, nicht nur `querySelector`.
- Für dynamische Ziele ist ein begrenzter `MutationObserver` oder ein wiederholter Resolver möglich; endloses Polling ist zu vermeiden.

### 10.3 Dialoge, Menüs, Tabs und Teleport

- Vuetify-Dialoge und -Menüs können in einem globalen Overlay-Container liegen. Der Resolver muss global suchen und z-index-kompatibel sein.
- Tour-Popover dürfen Dialogaktionen nicht verdecken oder Fokusfallen gegeneinander ausspielen.
- Tabs sollten über Komponentenstate beziehungsweise eine explizite Controller-Funktion umgeschaltet werden, nicht über simulierte DOM-Klicks.
- Expansion Panels werden nur geöffnet, wenn der Schritt sie benötigt. Der vorherige Zustand wird danach wiederhergestellt.
- Ein persistenter Recovery-Dialog hat Vorrang und blockiert Tourstarts.

### 10.4 Canvas und Drag-and-drop

- Ein Spotlight-Overlay kann Pointer- und Drag-Events abfangen.
- Interaktive Drag-and-drop-Schritte sollten entweder Interaktion ausdrücklich durchlassen oder als seitliche Checkliste ohne Canvas-Overlay laufen.
- maxGraph-Zellen sind keine stabilen Tourziele. Touren heften sich an Canvas, Palette oder Toolbar, nicht an konkrete SVG-Knoten.
- Nach Zoom, Sidebar-Resize oder schwebenden Fenstern muss die Library die Zielgeometrie aktualisieren.

### 10.5 Rollen und Sichtbarkeit

- Vor jedem Start werden Rolle und Route geprüft.
- Nicht-Admins dürfen keine Admin-Tour-ID als automatisch offen markiert bekommen, nur weil ein fehlerhaft sichtbarer Nav-Link existiert.
- Bedingte Schritte haben `when`-Prädikate; fehlende Ziele werden übersprungen und protokolliert.
- Ein übersprungener optionaler Schritt verhindert den Abschluss nicht.

### 10.6 Konflikte mit Fachzuständen

Touren starten nicht bei:

- Recovery-Dialog,
- Sync-Zustand `conflict`,
- laufendem Save/Load,
- offenem Confirm-Dialog für ungespeicherte Änderungen,
- Datei-Upload,
- zu kleinem Viewport,
- bereits laufender anderer Tour oder Hint.

## 11. Einführung in sinnvollen Phasen

### Phase 1 – belastbare Basis

- Tour-Registry und Library-Adapter,
- semantische Anker für `onboarding-v1` und `modeling-basics-v1`,
- lokaler, benutzerbezogener Status,
- manuelles Hilfe-/Tour-Center,
- Ready-/Abort-Mechanik und Desktop-Guard.

### Phase 2 – Kernworkflows

- `task-modeling-v1`, `model-versioning-v1`,
- `language-catalog-v1`, `language-authoring-v1`, `task-authoring-v1`,
- Backend-User-Preferences und Client-Cache.

### Phase 3 – Advanced Discovery

- Syntax- und Feedback-Touren,
- Feature Hints,
- anonymisierte Telemetrie zu Start, Abschluss, Abbruch und fehlendem Ziel, sofern Datenschutzkonzept und Einwilligung dies erlauben.

## 12. Abnahmekriterien für eine spätere Implementierung

- Kein Auto-Start vor bekannter Benutzer-ID und Rolle.
- Keine Tour auf `/login`, `/404` oder während Recovery/Konflikt.
- P0-Touren bleiben bei höchstens sechs Schritten.
- Kein Schritt führt ohne explizite Benutzeraktion eine fachliche Mutation aus.
- Alle optionalen Ziele können fehlen, ohne die Anwendung zu blockieren.
- Touren funktionieren mit leerem Modellkatalog und leerer Sprachliste.
- Admin- und Nicht-Admin-Erlebnis unterscheiden sich korrekt.
- Schließen, Abschließen und Snooze werden getrennt persistiert.
- Jede Tour ist manuell wiederholbar.
- Tastaturbedienung, Fokus, Kontrast und `prefers-reduced-motion` sind geprüft.
- Unterhalb der Desktop-Mindestbreite startet keine ungeeignete angeheftete Tour.

## 13. Konkreter Tour-Katalog

| ID | Name | Typ | Priorität | Zielgruppe | Trigger | Route | Schritte |
| --- | --- | --- | --- | --- | --- | --- | ---: |
| `onboarding-v1` | Einstieg in „My Models“ | Product Tour | P0 | alle neuen Benutzer | erster geladener Besuch | `/` | 4 |
| `modeling-basics-v1` | Erstes Modell bearbeiten | Product Tour | P0 | alle Modellierenden | erster geladener Modell-Workspace | `/modeling/:modelId` | 6 |
| `task-modeling-v1` | Mit einer Aufgabe modellieren | Product Tour | P1 | Benutzer mit Aufgabenmodell | erstes geladenes Aufgabenmodell | `/modeling/:modelId` | 5 |
| `model-versioning-v1` | Checkpoints, Releases und Timeline | Product Tour | P1 | alle Modellierenden | erster Checkpoint oder erste Timeline-Nutzung | `/modeling/:modelId` | 4 |
| `language-catalog-v1` | Sprachkatalog verwalten | Product Tour | P1 | Administratoren | erster Katalogbesuch | `/diagramLanguages` | 4 |
| `language-authoring-v1` | Sprache grundlegend bearbeiten | Product Tour | P1 | Administratoren | erste geladene konkrete Sprache | `/diagramLanguageEditor/:id` | 5 |
| `language-syntax-v1` | Syntax und Kardinalitäten | Product Tour | P2 | Sprachautoren | erster Wechsel auf Syntax mit Elementdaten | `/diagramLanguageEditor/:id` | 4 |
| `language-feedback-v1` | Feedback konfigurieren | Product Tour | P2 | Sprachautoren | erster Wechsel auf Feedback | `/diagramLanguageEditor/:id` | 5 |
| `task-authoring-v1` | Aufgabe erstellen und veröffentlichen | Product Tour | P1 | Administratoren | erster Task-Editor-Besuch | `/tasks` | 6 |
| `hint-connection-favorites-v1` | Verbindungen anheften | Feature Hint | P2 | Modellierende | zweite Nutzung der Palette | `/modeling/:modelId` | 1 |
| `hint-model-import-export-v1` | XML Import/Export | Feature Hint | P2 | Modellierende | erster Wechsel auf Import/Export | `/modeling/:modelId` | 1 |
| `hint-sample-solutions-v1` | Musterlösungen | Feature Hint | P2 | Benutzer mit passender Aufgabe | Button erstmals sichtbar | `/modeling/:modelId` | 1 |
| `hint-connection-settings-level-v1` | Verbindungs-Detailstufen | Feature Hint | P2 | Sprachautoren | erste Verbindung ausgewählt | `/diagramLanguageEditor/:id` | 1 |

## 14. Priorisierungsbegründung im Überblick

- **P0:** Ohne Orientierung auf `/` und ohne Verständnis von Sprachzuordnung, Palette, Canvas und Speichern kann ein neuer Benutzer den Kernnutzen nicht zuverlässig erreichen.
- **P1:** Aufgaben-, Versions-, Sprach- und Task-Autorenflows sind häufig beziehungsweise geschäftskritisch, betreffen aber nur einen Kontext oder eine Rolle.
- **P2:** Syntax, Feedback und kleine Feature Hints besitzen hohen Discovery-Wert, sind jedoch fortgeschritten, bedingt sichtbar oder leicht nachträglich erlernbar.

Damit bleibt das Erst-Erlebnis kurz, während komplexe Funktionen genau dort erklärt werden, wo Daten, Rolle und Motivation bereits vorhanden sind.
