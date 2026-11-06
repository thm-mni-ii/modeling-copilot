# Dagu

Dagu `2.16.6` orchestriert die Workflows des Modeling Copilot. Workflow-Schritte
laufen als Kubernetes Jobs im Namespace `workflow-runtime` mit dem Service
Account `workflow-runner`.

## Struktur

- `workflows/`: versionierte DAGs; aktuell enthält `hello.yaml` einen einfachen
  parallelen Beispiel-Workflow.
- `workflow-services/`: Container für Workflow-Schritte. `template-service/`
  zeigt einen einfachen JSON-Dienst; `graph-parser/` enthält den maxGraph-Parser.
  `workflow_io.py` stellt ausschließlich JSON-Dateizugriff und Laufkontext bereit.
  Dienstnamen beschreiben Fähigkeiten, keine Reihenfolge.
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

Das Backend überträgt Aufgabe, Modelle, Musterlösungen und alle benötigten
Sprachversionen einmalig als vollständigen gzip/Base64-Snapshot (aktuell maximal
100.000 Base64-Zeichen). Init prüft ihn und speichert ihn unveränderlich.
Danach greifen Dienste ausschließlich auf diesen Laufkontext und explizite
Zwischenstände zu; sie benötigen keinen Zugriff auf die Anwendungsdatenbank.

Der reguläre Ablauf in `workflows/model-evaluation-graph-matching.yaml` endet
aktuell nach **Init → parallelen Parsern → Veröffentlichung der Dateipfade**.
Der bestehende Dateiname bleibt für bereits ausgewählte Workflows erhalten;
eine fachliche Bewertung ist noch nicht implementiert.
`workflows/demo-model-evaluation.yaml` ergänzt ausdrücklich nur Demo-Platzhalter.
Reihenfolge und Parallelität stehen ausschließlich in den YAML-Dateien.

Alle Kubernetes-Jobs teilen den PVC `workflow-data` unter `/work/evaluations`:

```text
/work/evaluations/<evaluationId>/
  inputs/evaluation-input.json
  graphs/<modelKey>.json
  demo/                          # nur im Demo-Workflow
```

| Variable | Bedeutung |
| --- | --- |
| `WORKFLOW_EVALUATION_ID` | Wählt den initialisierten Laufkontext. |
| `WORKFLOW_DATA_ROOT` | Optionaler Speicherpfad statt `/work/evaluations`. |
| `WORKFLOW_INPUT_PATH` | Optionale Eingabedatei, relativ zum Laufordner. |
| `WORKFLOW_OUTPUT_PATH` | Optionaler Ausgabeort, relativ zum Laufordner. Unterschiedliche Aufrufe verwenden unterschiedliche Pfade. |

Ohne Eingabepfad kann jeder Dienst den ursprünglichen Snapshot direkt lesen:

```python
from workflow_io import workspace

store = workspace()
snapshot = store.snapshot()
task, models, languages = snapshot["task"], snapshot["models"], snapshot["languages"]
parsed = store.read("graphs/submission.json")
```

Der Parser wählt mit `MODEL_KEY` ein Modell aus dem Snapshot (Standard
`submission`). Dienste können fachliche Eingaben benötigen, kennen aber keine
festen Vorgängerschritte. Eigenständige Aufrufe erhalten ein JSON-Objekt über
`TEMPLATE_INPUT` oder stdin, beim Parser alternativ über `--input`.
Ein expliziter Eingabepfad und `TEMPLATE_INPUT` werden nicht gleichzeitig genutzt.

Austauschformate sind mit **vollständigen JSON-Beispielen und Felderklärungen**
bei [Init](workflow-services/workflow-data/README.md),
[Parser](workflow-services/graph-parser/README.md) und den Demo-Diensten beschrieben.
[Das Template](workflow-services/template-service/README.md) zeigt den einfachen
Entwicklungsvertrag. Diese Referenzen und die Python-Typhinweise laden keinen
Schema-Validator. Init und Parser prüfen benötigte Inhalte ausdrücklich im Code.
Die `params.schema`-Blöcke der DAGs sind davon getrennte Dagu-Parameterdefinitionen.

Dateien werden atomar veröffentlicht: identische Wiederholungen sind erlaubt,
abweichendes Überschreiben wird abgelehnt. Eingaben und Zwischenstände liegen
auf dem PVC, niemals im Projektordner. stdout wird zusätzlich als Dagu-Artefakt
für UI und API abgelegt. Das ist eine Anzeigekopie; der Datenaustausch erfolgt
über die expliziten Dateipfade. Der PVC wird nicht durch Dagu-History-Cleanup
bereinigt. `ReadWriteOnce` erlaubt parallele Jobs auf demselben Node.

Das folgt Dagu: [Dateien für größere Daten](https://docs.dagu.sh/writing-workflows/data-flow),
[Artefakte für gespeicherte Ausgaben](https://docs.dagu.sh/writing-workflows/artifacts).
Unsere Container sind gewöhnliche `k8s.run`-Jobs, keine paketierten
[Dagu Actions](https://docs.dagu.sh/dagu-actions/custom). Dafür ist kein eigenes
Capability-Manifest und kein JSON-Schema für die Dienst-JSON-Dateien erforderlich.

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
