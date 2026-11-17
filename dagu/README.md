# Dagu

Dagu `2.16.6` orchestriert die Workflows des Modeling Copilot. Workflow-Schritte
laufen als Kubernetes Jobs im Namespace `workflow-runtime` mit dem Service
Account `workflow-runner`.

## Struktur

- `workflows/`: ausschließlich `model-evaluation-graph-matching.yaml` mit seinen eingebetteten internen Modell- und Paarabläufen.
- `workflow-services/`: Container für Workflow-Schritte. `template-service/`
  zeigt den vorgesehenen Vertrag für JSON-Eingabe, JSON-Ausgabe und Exit-Codes.
- `infra/base.yaml`: gemeinsame Kubernetes-Vorgaben für Dev und Prod inklusive
  Namespace, Service Account und Ressourcenlimits.
- `infra/dev/`: Namespace-/Service-Account-Setup für Docker Desktop sowie die
  Anpassung der lokalen Kubeconfig für den Dagu-Container.
- `infra/prod/k3s-dagu.yaml`: K3s-Deployment mit RBAC, PVC, Service und
  Traefik-Ingress.

## Lokaler Betrieb

Voraussetzungen: Docker Desktop mit aktiviertem Kubernetes und eine vorhandene
Kubeconfig unter `~/.kube/config`.

```bash
kubectl config use-context docker-desktop
kubectl apply -f dagu/infra/dev/kubernetes.yaml
docker compose up -d dagu
```

Die Kubeconfig wird nur im Container angepasst: `127.0.0.1` beziehungsweise
`localhost` wird durch `host.docker.internal` ersetzt; die TLS-Prüfung verwendet
weiterhin `localhost`.

- UI: http://localhost:8525

Die Zugangsdaten sind reine Entwicklungswerte aus `docker-compose.yaml`.
Builtin-Authentifizierung ist aktiviert. Der initiale Admin wird nur beim ersten
Start des Datenvolumes angelegt.

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
ist `v21` (der interne Analyse-/Feedbackablauf ist `v13`), der Graphvergleich verwendet
intern `v13`, Synonym Matching `v4`. Graph Matching verwendet Serviceversion
`2.7.1`, Analytical Feedback `2.3.0`, Synonym Matching `1.3.0`, Feedback Generation
`2.2.1`, die übrigen Dienste `1.0.0`. Graphvergleich verwendet
`reference-comparison/v2`, Analyse/Feedback `/v3`, übrige Artefakte und vollständige
stdout-Envelopes `/v1`; Matcher-Fakten `1.1`, Identitätsevidenzen `1.1`.
Image-Tags: Analyse `v11`, Feedback `v10`, Matcher `v13`, Workflow-Data `v5`, Synonym `v4`, übrige `v1`.
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
Das Embedding-Modell wird beim Image-Build vorbereitet und während der Auswertung
offline geladen. Modellpaare laufen zunächst nacheinander mit eigenem
Speicherlimit von 2 GiB, Modellvorbereitung mit höchstens vier parallelen Läufen.

**Docker Desktop mit separatem Kubernetes-Image-Speicher:** Lokal gebaute Images
müssen zusätzlich im Kubernetes-Knoten verfügbar sein. Im vorhandenen
`docker-desktop`-Kontext mit dem Knoten `desktop-control-plane` kann die Übernahme
mit einer binären Pipe aus `cmd.exe` erfolgen (Tags bei Änderungen gemeinsam mit
Compose und Workflow aktualisieren):

```cmd
docker image save modeling-copilot/workflow-data:v5 modeling-copilot/graph-parser:v1 modeling-copilot/model-label-extraction:v1 modeling-copilot/synonym-matching:v4 modeling-copilot/one-to-one-graph-matching:v13 modeling-copilot/analytical-feedback:v11 modeling-copilot/feedback-generation:v10 | docker exec -i desktop-control-plane ctr -n k8s.io images import -
```

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

Das Manifest `infra/prod/k3s-dagu.yaml` stellt folgende Ressourcen bereit:

- Namespaces `dagu` und `workflow-runtime`
- Service Accounts und namespaced RBAC für Kubernetes Jobs und Pod-Logs
- Dagu Deployment, 5-GiB-PVC und ClusterIP-Service
- Traefik-Ingress unter `https://ikarus.mni.thm.de/dagu`

Der Init-Container klont den Branch `feat-add-dagu-as-workflow-manager` von
`https://github.com/thm-mni-ii/modeling-copilot.git`. Bei einem Wechsel des
Standard-Branches ist der Wert von `--branch` im Deployment anzupassen. Ein
Checkout auf dem Node oder ConfigMaps für Workflows und `base.yaml` sind nicht
erforderlich.

Zusätzlich wird im Namespace `dagu` folgendes Objekt erwartet:

- Secret `dagu-auth` mit den Keys `token-secret`, `admin-username` und
  `admin-password`

Deployment:

```bash
kubectl apply -f dagu/infra/prod/k3s-dagu.yaml
```

Produktive Zugangsdaten werden ausschließlich über das Secret `dagu-auth`
bereitgestellt.
