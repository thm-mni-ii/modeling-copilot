# Impuls-Fragen (Pulse Surveys) im Lernpfad

Kurze Fragen, die zufällig während der Aufgabenbearbeitung angeboten werden. Sie stören nicht, sind über Parameter steuerbar und lassen sich einfach wegklicken.

## 1. Fragen

Beide Fragen sind SurveyJS-`radiogroup`-Fragebögen (`rating` kann keine „nicht einschätzbar“-Option abbilden). Pflichtfrage, kein Kommentarfeld.

| Kennung             | Fragetext                                                                   | Skala                                            | Zusatzoption                        |
| ------------------- | --------------------------------------------------------------------------- | ------------------------------------------------ | ----------------------------------- |
| `RANDOM_UNDERSTAND` | Wie gut verstehst du gerade, was du bei dieser Aufgabe tun sollst?          | `1 – gar nicht`, `2`, `3`, `4`, `5 – sehr gut`   | `Kann ich gerade nicht einschätzen` |
| `RANDOM_NEED`       | Wie stark brauchst du gerade Unterstützung, um diese Aufgabe zu bearbeiten? | `1 – gar nicht`, `2`, `3`, `4`, `5 – sehr stark` | `Kann ich gerade nicht einschätzen` |

- Fragenamen: `random_understand`, `random_need`.
- Die Antwort wird als Choice-Text gespeichert. Die Auswertung liest die führende Ziffer, „nicht einschätzbar“ ergibt `null`.
- Fragen dürfen mehrfach beantwortet werden. Die Auswahl aus dem Pool ist immer uniform zufällig, ohne Ausschluss bereits beantworteter Fragen.

## 2. Template-Konfiguration

Optionales Feld `pulseSurveys` am Template (`learning_path_templates`). Alte Templates ohne Feld gelten als `enabled=false`, eine Migration ist nicht nötig. Die Konfiguration wird live vom Template gelesen und gilt sofort auch für laufende Runs.

| Parameter          | Typ         | Beschreibung                                                         | Startwert (Test)       |
| ------------------ | ----------- | -------------------------------------------------------------------- | ---------------------- |
| `enabled`          | bool        | Impulse aktiv                                                        | `true`                 |
| `surveyIds`        | UUID[]      | Pool, bei `enabled` mindestens 1                                     | beide Pulse-Fragebögen |
| `minGapSeconds`    | int         | Mindestabstand nach Anzeige, Antwort oder Wegklicken                 | `600` (10 min)         |
| `maxGapSeconds`    | int \| null | Obergrenze der Zufallsstreuung, `null` = exakt `minGapSeconds`       | `1800` (30 min)        |
| `maxPerSession`    | int         | Max. beantwortete Impulse pro Session                                | `3`                    |
| `maxPerTask`       | int \| null | Max. beantwortete Impulse pro Task-Step und Run, `null` = unbegrenzt | `null`                 |
| `minActiveSeconds` | int         | Kumulierte aktive Bearbeitungszeit am Task bis zum ersten Impuls     | `120`                  |
| `excludeStepIds`   | UUID[]      | Tasks ohne Impulse                                                   | `[]`                   |

Validierung (`PulseSurveyConfig`): sinnvolle Wertebereiche, `maxGapSeconds >= minGapSeconds`, `excludeStepIds` müssen existierende Steps sein, jeder Pool-Fragebogen muss veröffentlicht sein (`surveys.render(id, user, "use")`).

Eine Challenge (Time, Help Budget) unterdrückt Impulse nicht.

## 3. Entscheidungslogik (Server)

Der Server entscheidet, der Client sendet nur Signale. Persistenz: Collection `learning_path_pulse_events` (append-only, Index `(runId, stepId, at)`).

```
{ _id, runId, stepId, surveyId, sessionKey, event: "offered" | "answered" | "dismissed" | "expired", at }
```

`POST …/steps/{step}/pulse/poll` mit `{sessionKey, activeSecondsDelta}`. Der Server prüft der Reihe nach, bei der ersten Verletzung gilt `offer = null`:

1. `enabled`, Step ist ein geöffneter, nicht abgeschlossener Task und nicht in `excludeStepIds`.
2. `activeSecondsDelta` wird (begrenzt auf das Polling-Intervall) auf `activeSeconds` im Step-State addiert. Es gilt `activeSeconds >= minActiveSeconds`.
3. Kein Before- oder Completion-Fragebogen ist offen.
4. Zeitfenster: Nach jedem Event (`offered`, `answered`, `dismissed`, `expired`) wird ein zufälliger Abstand gezogen, gleichverteilt in `[minGapSeconds, maxGapSeconds]` (Seed aus `runId`, `stepId` und `offerSeq`, damit er stabil bleibt). Frühestens danach darf ein Angebot kommen.
5. Gezählt werden nur beantwortete Impulse: `answered` je Step und Run ist kleiner als `maxPerTask` (falls gesetzt), und `answered` je `sessionKey` ist kleiner als `maxPerSession`.
6. Zufällige Fragenauswahl aus `surveyIds`.
7. Ist bereits ein Angebot ohne Reaktion offen, wird dasselbe zurückgegeben. Ein Unique-Index auf `(runId, stepId, offerSeq)` verhindert Doppelangebote aus mehreren Tabs.

Weggeklickte Angebote zählen nicht in die Maxima, sie starten nur das Zeitfenster neu („wir versuchen es später erneut“). Dauerhaftes Wegklicken ist durch das Zeitfenster begrenzt, es kommt höchstens ein Angebot pro Fenster.

Unbeachtete Angebote erhalten nach dem visuellen Ablauf das Event `expired` mit `reason: "not_clicked"`. Sie zählen ebenfalls nicht als Antwort und starten das Zeitfenster neu. Der Server akzeptiert den Ablauf frühestens 40 Sekunden nach dem Angebot und nur, wenn noch keine Survey-Session geöffnet wurde. Öffnen und Ablauf werden pro Run serialisiert; ein bereits geöffnetes Angebot läuft nicht automatisch ab.

Session: ein Besuch der Modeling-View. Der Client erzeugt beim Mounten eine UUID als `sessionKey`.

### Endpunkte

| Endpunkt                            | Zweck                                        |
| ----------------------------------- | -------------------------------------------- |
| `POST …/steps/{step}/pulse/poll`    | Signale melden, Angebot erhalten oder `null` |
| `POST …/pulse/{offerId}/open`       | Fragebogen rendern und Session öffnen        |
| `POST …/pulse/{offerId}/dismiss`    | Event `dismissed`                            |
| `POST …/pulse/{offerId}/expire`     | Unbeachtetes Angebot als `expired` markieren |
| bestehende Survey-Session-Endpunkte | Absenden, danach Event `answered`            |

`open_path_session` bekommt den Slot `pulse:{offerId}`. Die Session-ID bleibt deterministisch, jedes Angebot erzeugt eine eigene Session, Mehrfachbeantwortung ist möglich.

## 4. Frontend

### Signale mit VueUse

Dafür wird `@vueuse/core` ergänzt (noch nicht in `web/package.json`).

| Zweck                            | VueUse                                           |
| -------------------------------- | ------------------------------------------------ |
| Inaktivität                      | `useIdle(timeout)`                               |
| Tabwechsel                       | `useDocumentVisibility()`                        |
| Browser-Fokus                    | `useWindowFocus()`                               |
| Zähltakt für aktive Sekunden     | `useIntervalFn(cb, 1000)` mit `pause` / `resume` |
| Polling (wartet auf das Promise) | `useTimeoutPoll(fn, interval)`                   |
| Reduzierte Animation             | `usePreferredReducedMotion()`                    |

Composable `usePulseSurvey(runId, stepId)` in der Modeling-View:

- `active = !idle && visibility === 'visible' && focused`.
- Der 1-s-Intervall zählt `activeSeconds` nur bei `active`. Der Server liefert mit `nextPollSeconds` den nächsten Abfrageabstand zwischen 1 und 30 Sekunden, passend zur verbleibenden aktiven Mindestzeit oder zum zufällig gewählten Zeitfenster. Das Polling pausiert bei `!active`, während ein Fragebogen offen ist und während der kurzen Bestätigung. Nach der Bestätigung wird sofort erneut abgefragt. So funktionieren auch konfigurierte Abstände von 1–10 Sekunden ohne eine zusätzliche feste 30-Sekunden-Pause.
- Zustände: `idle → offered → open → thanks`, bei unbeachtetem Angebot `offered → expired → idle`. Ein Angebot erscheint nie bei `!active`. Während des Abschieds nach Ablauf pausiert das Polling ebenfalls.

### Darstellung und Bedienung

- Der Pirat (`PulsePirateArt`) steht freigestellt ohne runden Button in einer hellen Inselszene oben in der rechten Sidebar. Ein hüpfender Münzhinweis macht auf die Frage aufmerksam. Münzsymbol mit Anzahl, „Zur Karte“ und „Abschließen“ liegen in einer Reihe direkt im Bild, ohne Überschrift oder separaten Balken. Die 160 Pixel hohe Szene bleibt über den scrollenden Werkzeugen sichtbar; die Sidebar startet mit 280 Pixeln Breite und lässt sich zwischen 280 und 440 Pixeln anpassen. Beim Hover und Tastaturfokus wird der Pirat etwas größer.
- Er lässt sich nur per Klick öffnen. Das Popover mit `SurveyRenderer` hat kein Scrim und keinen Fokus-Trap, die Arbeitsfläche bleibt bedienbar.
- Esc tut nichts: kein Esc-Handler, das Vuetify-Overlay ist `persistent` (kein Schließen per Esc oder Klick daneben).
- „Später“ (`dismiss`) steht nur im geöffneten Popover. Nach Wegklicken oder Absenden (`answered`) erscheint eine kurze Bestätigung.
- Ohne Klick erscheint nach 10 Sekunden die Sprechblase „Willst du eine Münze verdienen?“. Nach weiteren 10 Sekunden stoppt die Hinweisanimation. Ein kleiner goldener Zeitbalken unter dem Piraten läuft innerhalb von 20 Sekunden ab, während der Pirat zunehmend grau wird.
- Nach insgesamt 40 Sekunden wird `expired` gespeichert. Die Sprechblase wechselt zu „Ich komme später wieder.“; nach einem kurzen Moment blendet der Pirat aus. Bei Fehlern wird das Speichern erneut versucht. Öffnen des Fragebogens beendet den Ablauf; es läuft kein Countdown während der Beantwortung.
- Die SVG-Figur nutzt wenige Posen: neugierig, flitzend, einladend, zuh?rend, jubelnd und verabschiedend. Neue Angebote schauen kurz kopf?ber am oberen Modellrand herein und fliegen anschlie?end zur Insel. Der Auftritt dauert etwa 1,9 Sekunden und l?uft einmal pro Angebot. Bei Scrollen, Gr??en?nderungen oder ?ffnen der Frage endet er sofort; die Figur steht dann an ihrem Ziel. Der Auftritt wird au?erhalb der Sidebar gerendert, damit er nicht abgeschnitten wird.
- Bei Reduced Motion entfallen der animierte Auftritt, Jubelbewegung, Pulsieren, weiche Hover-Übergänge und Fade-Animation; Countdown, Sprechblasen und Ablaufstatus bleiben erhalten.

### Münzen und Bestätigung

Jeder beantwortete Impuls bringt eine Münze. Der Münzstand des Runs (`coins`) ergibt sich aus abgeschlossenen Aktivitäten plus den eindeutig gespeicherten `answered`-Events. Wiederholtes Absenden desselben Angebots erhöht ihn nicht erneut. Weggeklickte und abgelaufene Angebote bringen keine Münze. Auch bereits gespeicherte beantwortete Impulse werden beim Lesen des Münzstands berücksichtigt.

Die erfolgreiche Impuls-Abgabe liefert `rewardCoins: 1` und `coinBalance` zurück. Erst nach dieser Server-Bestätigung erscheint für etwa 3,8 Sekunden eine animierte Münze mit „+1 Münze verdient!“, einem Dank und dem Gesamtstand. Bei Reduced Motion bleibt die Münze statisch. Die Lernpfad-Karte zeigt `coins`; der Aufgabenfortschritt bleibt davon unabhängig.

Die Schatzreise-Karte erhält den Münzstand initial über `PathModelContext.coins` und aktualisiert ihn nach einer Impuls-Antwort aus `coinBalance`. Dafür gibt es keine zusätzliche regelmäßige Kontext-Abfrage. Auch während der Pflichtfragebögen bleibt die Rückkehr zur Lernpfad-Karte erreichbar.

### Editor

Eigenständiger Feature-Eintrag „Impuls-Fragen“ in der „Your path“-Ansicht von `ViewLearningPathEditor.vue`, oberhalb und klar getrennt von den Aktivitäten. Der Menüeintrag ist nur bei aktivierten Impulsen grün; die Auswahl wird unabhängig davon durch eine Umrandung markiert. Der mit „Konfiguration“ gekennzeichnete Eintrag öffnet das rechte Panel mit Aktivierungsschalter, Pool-Picker (Wiederverwendung von `LearningPathSurveyPicker.vue`), Zahlenfeldern für die Parameter und Mehrfachauswahl für `excludeStepIds`. Validierungsfehler öffnen ebenfalls dieses Panel. Die allgemeinen Path Settings enthalten keine Impuls-Konfiguration.

## 5. Testdaten (Seed)

Umsetzung in `api/src/modeling_api/db/initial_data.py`. Der Seed ist idempotent (`$setOnInsert`, feste IDs) und legt nie Runs oder Antworten an.

1. Das Anlegen von `survey_versions` und `surveys` aus `seed_survey_learning_path` wird zu `_seed_survey(survey_id, version_id, title, definition, created_at)` extrahiert und von beiden Seeds genutzt.
2. Zwei veröffentlichte Fragebögen mit festen IDs aus `uuid5(UUID(ORDER_MANAGEMENT_LEARNING_PATH_ID), "pulse:random_understand")` bzw. `…"pulse:random_need"`. Titel: `Example: RANDOM_UNDERSTAND (demonstration only)` und `Example: RANDOM_NEED (demonstration only)`.

   ```python
   LIKERT_UNSURE = "Kann ich gerade nicht einschätzen"

   def _pulse_definition(name, title, high):
       return Definition.model_validate({"elements": [{
           "type": "radiogroup", "name": name, "title": title, "isRequired": True,
           "choices": ["1 – gar nicht", "2", "3", "4", f"5 – {high}", LIKERT_UNSURE],
       }]}).model_dump(exclude_none=True)
   ```

3. Neues Beispiel-Template `uuid5(ORDER_MANAGEMENT_LEARNING_PATH_ID, "pulse-example")` (neu, weil `$setOnInsert` bestehende Dokumente nicht ändert): zwei bis drei `task`-Steps aus `tasks`, `published=True`, Name `Example: Modeling with random pulse questions`:

   ```python
   pulse_surveys={
       "enabled": True,
       "surveyIds": [understand_id, need_id],
       "minGapSeconds": 600,
       "maxGapSeconds": 1800,
       "maxPerSession": 3,
       "maxPerTask": None,
       "minActiveSeconds": 120,
       "excludeStepIds": [],
   }
   ```

   Zum schnellen Ausprobieren lassen sich die Werte im Editor senken, z. B. `minGapSeconds=30`, `maxGapSeconds=60`, `minActiveSeconds=20`.

## 6. Umsetzungsreihenfolge

1. Schema und Persistenz: `PulseSurveyConfig`, `SaveTemplate`, `template_meta`, `template_view`, Dokument-Schema, Event-Collection und Indizes in `db/client.py`.
2. Seed: `_seed_survey` extrahieren, beide Fragebögen und das Beispiel-Template.
3. `services/pulse_surveys.py` mit Entscheidungsfunktion und Endpunkten `poll`, `open`, `dismiss`.
4. Editor-Abschnitt.
5. `@vueuse/core` installieren, `usePulseSurvey` und die Pirat-Komponente in `ViewModeling.vue`.

Es sind keine Unit- oder Komponententests vorgesehen.
