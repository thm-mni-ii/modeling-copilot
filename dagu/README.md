# Dagu

Dagu `2.27.0` orchestriert die Workflows des Modeling Copilot. Die Workflow-Dienste
laufen dauerhaft („warm“) als Deployments im Namespace `workflow-runtime`
(`infra/workflow-services.yaml`). Dagu ruft sie je Schritt per `http.request` auf,
statt pro Schritt einen Kubernetes Job zu starten. Jeder Dienst führt dabei sein
unverändertes CLI-`main()` aus (`workflow-services/workflow_server.py`). Der
Response-Body ist die bisherige stdout-Ausgabe und wird wie zuvor zum Dagu-Artefakt.

## Struktur

- `workflows/`: ausschließlich `model-evaluation-graph-matching.yaml` mit seinen eingebetteten internen Modell- und Paarabläufen.
- `workflow-services/`: Container für Workflow-Schritte. `template-service/`
  zeigt den vorgesehenen Vertrag für JSON-Eingabe, JSON-Ausgabe und Exit-Codes.
- `infra/base.yaml`: gemeinsame Kubernetes-Vorgaben für Dev und Prod inklusive
  Namespace, Service Account und Ressourcenlimits.
- `infra/workflow-services.yaml`: warme Dienste (Deployments) und ein Service mit
  festem Port je Dienst (30081–30087) für den lokalen `workflow-sync`; die
  Produktionsdefinitionen sind in `../k3s-portainer.yaml` gespiegelt.
- `infra/dev/`: Namespace-/Service-Account-Setup für Docker Desktop, der
  NodePort-Zugang zu den Diensten sowie die Anpassung der lokalen Kubeconfig für
  den Dagu-Container.
- `../k3s-portainer.yaml`: zentrales Produktivdeployment inklusive Dagu,
  Workflow-Runtime, RBAC, PVCs und Traefik-Ingress.

## Lokaler Betrieb

Voraussetzungen: Docker Desktop mit aktiviertem Kubernetes und eine vorhandene
Kubeconfig unter `~/.kube/config`.

```bash
kubectl config use-context docker-desktop
docker compose up -d dagu
```

`docker compose up -d` aktualisiert die Workflow-Dienste ebenfalls automatisch.
Die Abhängigkeit `workflow-sync` läuft bei jedem Compose-Start einmal: Bei
geänderten Quellen oder fehlenden lokalen Images baut sie die Workflow-Images,
übernimmt geänderte Images binär in den kind-Knoten `desktop-control-plane`,
wendet die lokalen Kubernetes-Manifeste an und wartet auf erfolgreiche Rollouts.
Erst danach startet Dagu. Bei unveränderten Quellen werden Build und Import
übersprungen. Status und Fehler: `docker compose logs workflow-sync`.

Der Helfer benötigt den lokalen Docker-Socket und ist ausschließlich für die
Docker-Desktop-/kind-Entwicklung gedacht. Er löscht keine Laufdaten. DAG-Dateien
sind direkt eingebunden; Service-Code benötigt dagegen den Image-Rollout.
Versionsregeln stehen in [AGENTS.md](../AGENTS.md). Aktuelles Feedback:
Serviceversion `4.9.3`, Image `feedback-generation:v40`. Gespeicherte Berichte
bleiben unverändert; die neue Logik gilt bei einer neuen Berechnung.

Grundlage: [Dagu Compose](https://docs.dagu.sh/server-admin/deployment/docker-compose)
(DAG-Verzeichnis als Volume) und [Compose Build](https://docs.docker.com/reference/compose-file/build/)
(Unterscheidung von Build und Image-Pull). Ein Registry-Pull allein baut keinen
lokal geänderten Python-Code und aktualisiert keine Kubernetes-Deployments.

Dagu tritt dem Docker-Netz `kind` des Docker-Desktop-Kubernetes bei und erreicht
die Dienste über `WORKFLOW_SERVICES_HOST=desktop-control-plane` und die NodePorts.
Ohne Docker Desktop im kind-Modus fehlt dieses Netz; dann den Host und das Netz in
`docker-compose.yaml` anpassen.

Die Kubeconfig wird nur im Container angepasst: `127.0.0.1` beziehungsweise
`localhost` wird durch `host.docker.internal` ersetzt; die TLS-Prüfung verwendet
weiterhin `localhost`.

- UI: http://localhost:8525

Lokal ist die Anmeldung abgeschaltet (`DAGU_AUTH_MODE: none`). Ab Dagu 2.22
nimmt Dagu in diesem Modus nur bekannte Hostnamen an; IP-Adressen, `localhost`
und einteilige Namen wie `dagu` (API im Compose-Netz) sind immer erlaubt.
Weitere Namen bei Bedarf über `DAGU_ALLOWED_HOSTS` (kommagetrennt) freigeben.

## Workflows und Daten

Lokal ist `dagu/workflows/` schreibbar nach `/var/lib/dagu/dags` eingebunden.
Änderungen aus Repository oder UI betreffen daher dieselben Dateien. Laufdaten,
Logs und Wiki liegen getrennt im Docker-Volume `dagu-data`.

In Produktion holt ein Init-Container (`git-sync`) das öffentliche Repository
bei jedem Pod-Start per `git clone` in ein `emptyDir`-Volume. Der vollständige
Ordner `dagu/` wird unter `/app/dagu` eingebunden. Dagu liest die Workflows aus
`/app/dagu/workflows` und die Basiskonfiguration aus
`/app/dagu/infra/base.yaml`. Ein Host-seitiger Checkout ist nicht nötig, da
Portainer nur das Manifest anwendet. Laufdaten, Logs und Wiki liegen auf dem
PVC `dagu-data`.

### Datenfluss einer Auswertung

Das Backend übergibt Modelle und Sprachversionen als vollständigen Snapshot.
`workflow-data` speichert ihn auf dem gemeinsamen PVC unter
`/work/evaluations/<evaluationId>/inputs/evaluation-input.json`.
`model-evaluation-graph-matching` führt die Phasen 1 bis 6 aus: Initialisierung,
Graph-Parsing und Elementinventar je Modell, anschließend semantisches Matching
einen vorläufigen Graphvergleich, analytische Profile und aggregiertes Feedback je Musterlösung. Graphen liegen unter `graphs/<modelKey>.json`,
Inventare unter `labels/<modelKey>.json` und semantische Kandidaten unter
`candidates/<referenceKey>.json`; Vergleiche liegen unter
`comparisons/<referenceKey>.json` und Feedbackberichte unter
`feedback/<referenceKey>.json`. Analysen liegen unveränderlich unter
`analysis/<referenceKey>/<analysisKey>.json`. Die Abgabe wird nur einmal vorbereitet.
Alle benötigten Modell- und Paarabläufe sind intern in derselben Datei eingebettet.
Dagu registriert ausschließlich `model-evaluation-graph-matching`. Die Workflowversion
ist `v30` (der interne Analyse-/Feedbackablauf ist `v17`), der Graphvergleich verwendet
intern `v22`, Synonym Matching `v9`, der Signalexport `synonym-signals-pair` `v1`, Parser und Inventar `v2`.
Der interne Ablauf `synonym-signals-model` (`v3`) berechnet fehlende `synonym-signals/v1` aus eingefrorenen Snapshots nach.

Das Synonym-Glossar zeigt zusätzlich die tatsächlich im finalen Nutzerfeedback
mitgezählten Begriffe. Die Zuordnung stammt aus dem Analyseartefakt und wird nur
verwendet, wenn dessen Erkennungsübersicht mit dem finalen Feedback übereinstimmt.
Fehlende historische Artefakte bleiben unbekannt. Bei mehreren Musterlösungen
wird auch ausgewiesen, ob die betrachtete Lösung die beste Nutzerquote liefert.

Die Spalte „Evidence“ zeigt neben den Textwerten den Grund jeder Entscheidung als Tag
mit kurzer Hover-Erklärung, weil auch ein hoher Textwert abgelehnt werden kann.
„Partially recognized“ steht für einen passenden Begriff, dessen übergeordnetes Element
nicht identifiziert ist. Dieser Status ändert die Lernendenquote nicht. Ein Treffer an
einem gleichnamigen Element in dessen eigener Struktur erscheint als „Same name elsewhere“.
Die Regeln stehen unter GM-40 in `docs/graph-matching-workflow/04-GRAPH-MATCHING.md`.

Akzeptierte Synonyme lassen sich mit „Use as matching source“ direkt als weitere
Vergleichstexte aktivieren. „Manage sources“ zeigt die aktiven Quellen. Es gibt
keinen Bestätigungsdialog und keine numerischen Quellen- oder Textpaarlimits.
Die Änderung bleibt durch die Glossarrevision gegen parallele Bearbeitung geschützt.
Bei Ablehnung, Ignorieren oder Entfernen endet die Quellfreigabe; Imports übernehmen
sie nicht. Die Leiste zeigt Baseline, zusätzliche Vergleiche und Gesamtzahl mit
prozentualem Aufschlag und einer von Grün bis Dunkelrot abgestuften Farbe.
Die Schätzung nutzt die gespeicherten Vergleichsmatrizen der verfügbaren originalen
Auswertungen; die Abdeckung steht im Tooltip. Fehlen diese, werden Referenztexte
gezählt. Beides beschreibt Vergleichsmengen, keine Laufzeitprognose.

Neue Läufe frieren `matchingSource: true` und den Ausgangstext `term` im Glossar
ein. Synonym Matching berechnet für diese Texte zusätzliche Werte gegen die
zulässigen Abgabetexte. Originalwerte bleiben unverändert;
`matchingSources` im Kandidatenartefakt führt die zusätzlichen Werte separat.
Der Graphmatcher prüft die Freigabe gegen den Eingabesnapshot und wählt pro Paar
die stärkste zulässige Textevidenz, ohne Methoden verschiedener Quellen zu mischen.
Schwellen, Textschutzregeln und Eindeutigkeit gelten weiterhin. Dies gilt auch für
eigenen Verbindungstext. Verwendete Quellen stehen als `sourceTerm` in der
Identitätsevidenz und in der aufklappbaren Glossar-Evidenz. Es gibt keine automatische
Weiterfreigabe neu gefundener Begriffe und keine rekursive Synonymkette.

„Why suggested?“ erklärt direkt in der Tabelle den Kandidatengrund und die
verbleibende Unsicherheit. „Learner result“ zeigt mitgezählte Fälle und fehlende
Ergebnisse getrennt; fehlende Ergebnisse werden nicht als Ablehnung gezählt.
Die aktuelle Evidenzansicht unterteilt jeden Begriff nach kategorisch gleichen
aufgezeichneten Vorbedingungen: Parent, Typverträglichkeit, Kinderstruktur und
Verbindungsendpunkte sowie gegebenenfalls dem eingefrorenen Glossarstand.
Unterschiedliche gespeicherte Textschwellen bilden ebenfalls getrennte Gruppen.
Jede Gruppe erhält eigene Fallzahlen, Textwerte, Entscheidungsgründe und Ergebnisse;
das Ergebnis selbst bestimmt die Gruppe nicht. Fehlender oder nur teilweise
aufgezeichneter Kontext bleibt von vollständigen Kontextnachweisen getrennt.
Die Modell-/Tabellenaufteilung ist über eine per Maus und Tastatur bedienbare
Trennleiste veränderbar. Accept, Reject und Ignore stehen vollständig sichtbar
untereinander. Die Review-Liste enthält auch bereits mitgezählte Begriffe ohne
manuelle Glossarentscheidung; im Ergebnis-Tab lassen sich bestehende Entscheidungen
ebenfalls ändern. Textähnlichkeiten erscheinen direkt als Prozentwerte mit
aufklappbaren Wortpaaren. Die Werte sind Ähnlichkeitsscores, keine Erfolgswahrscheinlichkeit;
die Zählquote verwendet ausschließlich verifizierte Fälle. Fehlende Zählentscheidungen
bleiben separat sichtbar. Alle Angaben sind modellierungssprachenunabhängig.
„Explain result“ öffnet einen ausgewählten Submission-Fall mit einer kurzen
Erklärung. Weitere Fälle lassen sich auswählen. Technische Kriterien, Textwerte,
Schwellen und Alternativen bleiben zunächst eingeklappt. Die API liest historische
Artefakte bei Auswahl eines Falls; dabei wird keine neue Auswertung gestartet.
Einzelpaar-Nachweise werden von über alle Alternativen aggregierten Kriterien
unterschieden. Fehlende Nachweise benennen die betroffene Quelle; gespeicherte
Synonymvorschläge werden auch ohne lesbare Originalartefakte zugänglich gehalten.
Bei teilweise ausgewerteten Modellen zählt der gespeicherte Auswertungsstatus des
konkreten Elements, damit ein ausgewertetes, nicht erkanntes Element nicht pauschal
als unbekannt erscheint. Vorhandene verifizierte Ergebnisse bleiben erhalten, wenn
sich die ursprünglichen Detailartefakte später nicht mehr laden lassen.

„Compare full evaluations“ startet den internen Wrapper `evaluation-replay` (`v2`),
der den vollständigen aktuellen `model-evaluation-graph-matching`-Ablauf auf den
gespeicherten Abgabeversionen erneut ausführt. Pro Modellversion wird die letzte
erfolgreiche Nicht-Staff-Auswertung herangezogen. Alle Musterlösungen des Releases
werden berücksichtigt. Der aktuelle Glossarstand und optionale Textschwellen
werden bei Vergleichsbeginn eingefroren; ohne eigene Schwellen gelten die aktuellen
Workflowstandards. Neue Läufe starten beim Statusabruf (höchstens zwei gleichzeitig),
bereits gestartete Läufe laufen auch nach Schließen der Ansicht zu Ende.

Die Collections `evaluation_replays` und `evaluation_replay_results` sind vollständig
von den regulären Auswertungen und Synonymvorschlägen getrennt. MongoDB-TTL-Indizes
löschen beide nach sieben Tagen ab Vergleichsbeginn. Pro Release bleiben höchstens
drei Vergleiche erhalten; der älteste abgeschlossene wird beim nächsten Start
entfernt. Abgeschlossene Vergleiche lassen sich zusätzlich manuell löschen.
Der Wrapper entfernt seinen mit `replay-` gekennzeichneten Arbeitsordner im
Exit-Handler auch nach einem Laufabbruch. Dagu hält Logs und Artefakte sieben Tage
vor; manuelles Löschen in der Anwendung entfernt zunächst die Datenbankergebnisse.
Verwaiste temporäre Arbeitsordner werden beim nächsten Workflow-Data-Aufruf nach
sieben Tagen entfernt. Reguläre Auswertungsordner werden nicht gelöscht.

Graph Matching verwendet Serviceversion
`2.16.0`, Analytical Feedback `2.4.0`, Synonym Matching `1.7.0`, Feedback Generation
`4.10.0`, Workflow-Data `1.4.0`, die übrigen Dienste `1.0.0`. Graphvergleich verwendet
`reference-comparison/v2`, Analyse/Feedback `/v3`, übrige Artefakte und vollständige
stdout-Envelopes `/v1`; Matcher-Fakten `1.1`, Identitätsevidenzen `1.1`.
Image-Tags: Analyse `v13`, Feedback `v41`, Matcher `v24`, Workflow-Data `v11`, Synonym `v11`, Parser und Inventar `v2`.
`workflow-data` friert zusätzlich `graphMatching.hints` ein (`textBand` 0,05, `minimumNeighbors` 2,
`minimumChildren` 2, `showReferenceText` als Probe aktiv). Der Matcher leitet daraus Hinweise ab, die nie zählen
(GM-41 bis GM-44 in `docs/graph-matching-workflow/04-GRAPH-MATCHING.md`); Lernende sehen sie in einer eigenen Ansicht.
Replays speichern je Musterlösung zusätzlich `pairs`, `hints` und `decisionRounds` für den paarweisen Vergleich.
Jede Auswertung verwendet die Evidenzstufen: `workflow-data` friert vor dem Eingabehash
`graphMatching.textEvidence.tiers` (kanonisch gleich → Schreibvariante → Bedeutung) mit
`semantics.methods: [damerau_canonical, multilingual_expanded]` in `comparisonConfig` ein.
Standardschwellen: Schreibvariante 0,85, Bedeutung 0,85, Graubereich ab 0,70. Der optionale
Workflowparameter `text_evidence` überschreibt sie als JSON-Objekt (`spelling`, `meaning`,
`meaningFloor`; nur Admins über den Startdialog). Konzept unter
`docs/graph-matching-workflow/07-KONZEPT-TEXTEVIDENZ-STUFEN.md`.
Lokale Nachweise vom 16.11.2026: [Graph-Evaluation](../docs/graph-evaluation/RUNLOG.md).

Der Analyse-/Feedbackablauf liest `analysisPath` und `analysisKey` aus dem vollständigen
Analyse-stdout und veröffentlicht sie über `stdout.outputs`. Der Filter prüft Status,
Pfadformat und die Übereinstimmung des Schlüssels mit dem Dateinamen, bevor der
Feedback-Service startet. Die früher lokal gecachten `v1`-Analyse-Images lieferten
stattdessen nur `{status, path, sizeBytes}`; mit `v2` wurde die vollständige
JSON-Ausgabe bereitgestellt. Die früheren `v4`-Tags ergänzten den analytischen
Vertrag 1.1; `v5` ergänzte die Projektion der Matcher-Fakten. `v6` ergaenzte
die getrennte Identitaets- und Positionscheckliste. Workflow v8, Matcher-Image v4
und Analyse-/Feedback-Images v8 veroeffentlichen kompakte v3-Analyse-/Feedback-Vertraege mit einer
verbindlichen Erkennungsuebersicht. Details und lokale Nachweise stehen im
[Cleanup-Bericht](workflow-services/analytical-feedback/CLEANUP.md).
Beide JSON-stdout-Artefakte bleiben für das Frontend erhalten;
Synonym Matching und seine Parameter sind unverändert.

Lokal am 14.11.2026 geprüft: gespeichertes Analyseartefakt erfolgreich übergeben;
fehlende Metadaten, `<nil>` und widersprüchliche Schlüssel blockieren den Verbraucher.
Anschließend ausschließlich `analytical-feedback-pair` für `reference_1` der Auswertung
`5be758db-59e8-4e0d-93ba-309a4e4eab3a` erfolgreich ausgeführt
(Lauf `034xSoJWjr7s9XNA7LIxaH`), mit vollständigen Analyse- und Feedbackausgaben.
Diese Laufprüfung betrifft den früheren stdout-Fix. Die Evidenzrevision ist mit
165 gezielten lokalen Tests einschließlich gespeicherter Modelle Baseline, M02,
M03, M05, M06a/b und M08, Schema-/Frontendadapterprüfung, Lint und Typprüfung verifiziert.
Die damaligen Images (`one-to-one-graph-matching:v3`,
`analytical-feedback:v6`, `feedback-generation:v6`) wurden gebaut und mit
identischen Digests in Docker und im lokalen Kubernetes-Image-Speicher geprüft;
die Workflow-Spezifikation wurde per MCP validiert. Für diese Änderung wurden
keine Pipeline, Embeddingberechnung oder Kubernetes-Jobs gestartet.
Die Modellprüfungen verwenden vollständige generische Kompatibilitätskandidaten,
keine neu berechneten Synonymscores oder historische eingefrorene Kandidatenketten.

`WORKFLOW_EVALUATION_ID` wählt den Laufordner, `MODEL_KEY` das Parsermodell.
`WORKFLOW_INPUT_PATH` und `WORKFLOW_OUTPUT_PATH` wählen relative JSON-Dateipfade;
`WORKFLOW_DATA_ROOT` überschreibt das Basisverzeichnis. Dienste benötigen keinen
Datenbankzugriff. Details: [Graph Parser](workflow-services/graph-parser/README.md)
und [Init](workflow-services/workflow-data/README.md).

### Im Browser ausprobieren

Die Aufgabe muss den Workflow `model-evaluation-graph-matching` und mindestens
eine freigegebene Musterlösung enthalten. Nach dem Speichern der Abgabe startet
der Auswertungsbutton im Aufgabenbereich einen neuen Lauf. Die Auswertungs-Sidebar
zeigt Graph und Elementinventar für Abgabe und Musterlösungen sowie einen Schritt
„Semantische Kandidaten“ und „Vorläufiger Graphvergleich“ je Musterlösung.
Die Serviceansicht zeigt außerdem das vorläufige Feedback je Musterlösung.
Der Schritt „Analytisches Feedback“ zeigt Moderatoren und Administratoren die
kompakten elementbezogenen Hinweise. Das Analyseartefakt liegt zusätzlich im
Workflow-Workspace. Der Feedbackbericht wird im selben Referenz-Unterlauf unter
Verwendung dieses Analyseartefakts erzeugt. Details und Aussagegrenzen:
[Analytical Feedback](workflow-services/analytical-feedback/README.md).
Die Uebersicht zeigt eindeutig erkannte Referenzobjekte insgesamt und je vorhandener Vergleichsgruppe oder nicht gruppiertem Typ. Die Erkennungsquote ist keine Korrektheitsquote und keine Note.
Vorlaeufige Matcher-Metriken sind ausschliesslich optionale Entwicklungsdiagnosen. „Ausklappen“, „Groß anzeigen“ und
„Als JSON kopieren“ öffnen beziehungsweise exportieren die vollständigen
Zwischenergebnisse. Auch bei einem späteren Schrittfehler bleiben die bereits
erzeugten Ergebnisse sichtbar. Die Ergebnisübersicht benennt die erreichte Phase;
endgültige Zuordnungen, vollständige strukturelle Bewertung und Punkte
sind noch nicht Teil dieses Workflows.

Lokal nur die tatsächlich benötigten Images bauen:

```powershell
docker compose --profile workflow-services build workflow-data workflow-graph-parser workflow-model-label-extraction workflow-synonym-matching workflow-one-to-one-matching workflow-analytical-feedback workflow-feedback-generation
docker compose up -d --no-deps --build api
```

Die benötigten Image-Tags stehen in `docker-compose.yaml` und stimmen mit dem
Workflow überein. Der Synonym-Service verwendet den eigenen Ordner
`workflow-services/synonym-matching`; der Methodenreferenzordner bleibt unverändert.
Das Embedding-Modell wird beim Image-Build vorbereitet und beim Start des warmen
Synonym-Dienstes einmal offline geladen; erst danach meldet der Pod Bereitschaft.
Modellpaare laufen nacheinander, Modellvorbereitung mit höchstens vier parallelen
Läufen. Jede Replik bearbeitet Anfragen strikt nacheinander; Parallelität entsteht
über weitere Repliken hinter dem Service.

**Docker Desktop mit separatem Kubernetes-Image-Speicher:** Lokal gebaute Images
müssen zusätzlich im Kubernetes-Knoten verfügbar sein. Im vorhandenen
`docker-desktop`-Kontext mit dem Knoten `desktop-control-plane` kann die Übernahme
mit einer binären Pipe aus `cmd.exe` erfolgen (Tags bei Änderungen gemeinsam mit
Compose und Workflow aktualisieren):

```cmd
docker image save modeling-copilot/workflow-data:v11 modeling-copilot/graph-parser:v2 modeling-copilot/model-label-extraction:v2 modeling-copilot/synonym-matching:v11 modeling-copilot/one-to-one-graph-matching:v24 modeling-copilot/analytical-feedback:v13 modeling-copilot/feedback-generation:v41 | docker exec -i desktop-control-plane ctr -n k8s.io images import -
```

Danach `kubectl apply -f dagu/infra/workflow-services.yaml`; bei geänderten Tags
rollen die Deployments automatisch neu aus.

Die Pipe in `cmd.exe` ausführen; ältere PowerShell-Versionen können binäre
Image-Daten beim Weiterreichen als Text beschädigen. Nach jedem lokalen Build
müssen die betroffenen Image-Tags erneut in den Kubernetes-Knoten importiert werden.
Bei einer anderen lokalen Kubernetes-Installation stattdessen deren Image-Import
oder eine erreichbare Registry verwenden. Keine produktiven Cluster hierfür
verändern. Die Images werden mit `IfNotPresent` gestartet; ein bereits
gecachtes Image wird nicht automatisch durch einen neuen Docker-Build ersetzt.

Die API liest große Zwischenresultate über Dagu-Artefakte und die kleine
Abschlussübersicht über den `/outputs`-Endpunkt. So wird nicht das letzte
Elementinventar als vermeintliches Gesamtergebnis verwendet.

## Produktion (K3s/Portainer)

Das zentrale Manifest stellt die Anwendung, Dagu und die gemeinsame
Workflow-Laufzeit einschließlich der warmen Workflow-Dienste bereit. Siehe
[`k3s-portainer.yaml`](../k3s-portainer.yaml). Die Service-Definitionen sind
dort enthalten, damit Portainer das Produktivdeployment mit einem Manifest
vollständig anlegen kann. Für den lokalen Betrieb verwendet `workflow-sync`
weiterhin `infra/workflow-services.yaml`; Änderungen an den Service-Deployments
müssen in beiden Manifesten nachvollzogen werden. Die lokalen Images und Tags
unterscheiden sich von den veröffentlichten GHCR-Images in Produktion.

- Namespace `modeling-copilot` für Anwendung und Dagu
- Namespace `workflow-runtime` für die dynamischen Workflow-Jobs und warmen
  Workflow-Dienste
- Service Accounts und namespaced RBAC für Kubernetes Jobs und Pod-Logs
- Dagu Deployment, 5-GiB-PVC und ClusterIP-Service
- Traefik-Ingress unter `https://ikarus.mni.thm.de/dagu`

Die warmen Workflow-Dienste werden als ClusterIP (nicht von außen erreichbar)
im Namespace `workflow-runtime` bereitgestellt. Dagu erreicht sie über
`WORKFLOW_SERVICES_HOST=workflow-services.workflow-runtime.svc.cluster.local`.
Die Deployments beziehen die öffentlichen GHCR-Images mit `latest` und
`imagePullPolicy: Always`. Das PVC ist `ReadWriteOnce`;
alle Repliken müssen daher auf dem Knoten laufen, der es eingebunden hat.

Der Init-Container klont den Branch `main` von
`https://github.com/thm-mni-ii/modeling-copilot.git`. Bei einem Wechsel des
Standard-Branches ist der Wert von `--branch` in `k3s-portainer.yaml`
anzupassen. Ein Checkout auf dem Node oder ConfigMaps für Workflows und
`base.yaml` sind nicht erforderlich.

Zusätzlich wird im Namespace `modeling-copilot` folgendes Objekt erwartet:

- Secret `dagu-auth` mit den Keys `token-secret`, `admin-username` und
  `admin-password` (Token-Secret mindestens 32, Passwort mindestens 8 Zeichen)
- Nach dem ersten Start zusätzlich `api-key` im selben Secret für die API

Dagu läuft mit Builtin-Anmeldung. Der initiale Admin aus dem Secret wird nur
angelegt, solange der Benutzerspeicher auf dem PVC leer ist; spätere Änderungen
am Secret ändern ihn nicht. Builtin-Login, erster Admin und bis zu zwei API-Keys
sind ohne Lizenz nutzbar; weitere Benutzer, Rollen und OIDC erfordern eine
Dagu-Lizenz. Den API-Key für das Backend (`DAGU_API_KEY`) legt der Admin in der
UI unter Admin > API Keys mit Rolle `operator` und Zugriff auf die REST-API an.

In Portainer **Use namespace(s) specified from manifest** aktivieren und das
zentrale Manifest deployen. Über die Kommandozeile genügt dafür:

```bash
kubectl apply -f k3s-portainer.yaml
```

Produktive Zugangsdaten werden ausschließlich über das Secret `dagu-auth`
bereitgestellt. Nach dem ersten Start als Administrator unter
`https://ikarus.mni.thm.de/dagu` anmelden, unter **API Keys** einen Schlüssel
mit Rolle `operator` erzeugen und als `api-key` im Secret hinterlegen.
Anschließend die API neu starten. Bis dahin startet die Anwendung bereits,
Auswertungen benötigen jedoch den Schlüssel.

Die API verwendet intern `http://dagu:8080/dagu`. Dagu darf Jobs und deren
Logs ausschließlich in `workflow-runtime` verwalten. Der ServiceAccount der
Workflow-Jobs erhält kein automatisch eingebundenes Kubernetes-Token.

Die Release-Pipeline veröffentlicht die sieben im Auswertungsworkflow
verwendeten Service-Images unter `ghcr.io/thm-mni-ii/modeling-copilot-*`
bei einem Release-Tag. Diese GHCR-Pakete müssen für das vorliegende Deployment
öffentlich lesbar sein. Insbesondere muss `modeling-copilot-analytical-feedback`
erst durch einen erfolgreichen Release-Lauf veröffentlicht werden, bevor sein
Deployment starten kann. Ein Merge allein veröffentlicht kein Image.

Falls das frühere separate Dagu-Deployment bereits verwendet wurde, müssen
Secret und persistente Dagu-Daten vor dem Wechsel in den Namespace
`modeling-copilot` übernommen werden. Das zentrale Manifest überträgt
vorhandene PVC-Daten aus dem Namespace `dagu` nicht automatisch.
