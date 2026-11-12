# Dagu

Dagu `2.16.6` orchestriert die Workflows des Modeling Copilot. Workflow-Schritte
laufen als Kubernetes Jobs im Namespace `workflow-runtime` mit dem Service
Account `workflow-runner`.

## Struktur

- `workflows/`: Hauptworkflow für die Modellauswertung und `hello.yaml` als
  einfacher Testworkflow.
- `workflow-services/`: Container für Workflow-Schritte. `template-service/`
  zeigt den vorgesehenen Vertrag für JSON-Eingabe, JSON-Ausgabe und Exit-Codes.
- `infra/base.yaml`: gemeinsame Kubernetes-Vorgaben für Dev und Prod inklusive
  Namespace, Service Account und Ressourcenlimits.
- `infra/dev/`: Namespace-/Service-Account-Setup für Docker Desktop sowie die
  Anpassung der lokalen Kubeconfig für den Dagu-Container.
- `../k3s-portainer.yaml`: zentrales Produktivdeployment inklusive Dagu,
  Workflow-Runtime, RBAC, PVCs und Traefik-Ingress.

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
einen vorläufigen Graphvergleich und aggregiertes Feedback je Musterlösung. Graphen liegen unter `graphs/<modelKey>.json`,
Inventare unter `labels/<modelKey>.json` und semantische Kandidaten unter
`candidates/<referenceKey>.json`; Vergleiche liegen unter
`comparisons/<referenceKey>.json` und Feedbackberichte unter
`feedback/<referenceKey>.json`. Die Abgabe wird nur einmal vorbereitet.
Die internen Modell- und Paarworkflows sind in derselben Datei eingebettet.
`hello` bleibt der einfache Testworkflow.

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
Der Vergleich zeigt Ankerabdeckung, maximale Zuordnungskapazität und ein
Intervall der vorläufigen Zugehörigkeitskonsistenz. Diese Zahlen sind keine
bestätigte Modellübereinstimmung. „Ausklappen“, „Groß anzeigen“ und
„Als JSON kopieren“ öffnen beziehungsweise exportieren die vollständigen
Zwischenergebnisse. Auch bei einem späteren Schrittfehler bleiben die bereits
erzeugten Ergebnisse sichtbar. Die Ergebnisübersicht benennt die erreichte Phase;
endgültige Zuordnungen, vollständige strukturelle Bewertung und Punkte
sind noch nicht Teil dieses Workflows.

Lokal nur die tatsächlich benötigten Images bauen:

```powershell
docker compose --profile workflow-services build workflow-data workflow-graph-parser workflow-model-label-extraction workflow-synonym-matching workflow-one-to-one-matching workflow-feedback-generation
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
docker image save modeling-copilot/workflow-data:latest modeling-copilot/graph-parser:latest modeling-copilot/model-label-extraction:latest modeling-copilot/synonym-matching:latest modeling-copilot/one-to-one-graph-matching:latest modeling-copilot/feedback-generation:latest | docker exec -i desktop-control-plane ctr -n k8s.io images import -
```

Die Pipe in `cmd.exe` ausführen; ältere PowerShell-Versionen können binäre
Image-Daten beim Weiterreichen als Text beschädigen. Nach jedem lokalen Build
müssen die `latest`-Images erneut in den Kubernetes-Knoten importiert werden.
Bei einer anderen lokalen Kubernetes-Installation stattdessen deren Image-Import
oder eine erreichbare Registry verwenden. Keine produktiven Cluster hierfür
verändern. Die Images werden mit `IfNotPresent` gestartet; ein bereits
gecachtes Image wird nicht automatisch durch einen neuen Docker-Build ersetzt.

Die API liest große Zwischenresultate über Dagu-Artefakte und die kleine
Abschlussübersicht über den `/outputs`-Endpunkt. So wird nicht das letzte
Elementinventar als vermeintliches Gesamtergebnis verwendet.

## Produktion (K3s/Portainer)

Das zentrale Manifest stellt die Anwendung und ihre Workflow-Infrastruktur
gemeinsam bereit. Siehe [`k3s-portainer.yaml`](../k3s-portainer.yaml).

- Namespace `modeling-copilot` für Anwendung und Dagu
- Namespace `workflow-runtime` für die dynamischen Workflow-Jobs
- Service Accounts und namespaced RBAC für Kubernetes Jobs und Pod-Logs
- Dagu Deployment, 5-GiB-PVC und ClusterIP-Service
- Traefik-Ingress unter `https://ikarus.mni.thm.de/dagu`

Der Init-Container klont den Branch `main` von
`https://github.com/thm-mni-ii/modeling-copilot.git`. Ein
Checkout auf dem Node oder ConfigMaps für Workflows und `base.yaml` sind nicht
erforderlich.

Zusätzlich wird im Namespace `modeling-copilot` folgendes Objekt erwartet:

- Secret `dagu-auth` mit den Keys `token-secret`, `admin-username` und
  `admin-password`
- Nach dem ersten Start zusätzlich `api-key` im selben Secret für die API

In Portainer **Use namespace(s) specified from manifest** aktivieren und das
zentrale Manifest deployen. Über die Kommandozeile erfolgt das Deployment mit
folgendem Befehl.

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

Die Release-Pipeline veröffentlicht die sechs im Auswertungsworkflow
verwendeten Service-Images unter `ghcr.io/thm-mni-ii/modeling-copilot-*`.
Diese GHCR-Pakete müssen für das vorliegende Deployment öffentlich lesbar
sein. Der produktive Init-Container ersetzt die lokalen Image-Namen in seiner
geklonten Workflow-Kopie durch die GHCR-Namen und setzt dort die Pull-Policy
auf `Always`, damit neue Jobs das veröffentlichte `latest`-Image beziehen.

Falls das frühere separate Dagu-Deployment bereits verwendet wurde, müssen
Secret und persistente Dagu-Daten vor dem Wechsel in den Namespace
`modeling-copilot` übernommen werden. Das zentrale Manifest überträgt
vorhandene PVC-Daten aus dem Namespace `dagu` nicht automatisch.
