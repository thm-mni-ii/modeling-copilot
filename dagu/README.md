# Dagu

Dagu `2.16.6` orchestriert die Workflows des Modeling Copilot. Workflow-Schritte
laufen als Kubernetes Jobs im Namespace `workflow-runtime` mit dem Service
Account `workflow-runner`.

## Struktur

- `workflows/`: versionierte DAGs; aktuell enthält `hello.yaml` einen einfachen
  parallelen Beispiel-Workflow.
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
- Benutzer: `admin`
- Passwort: `dev-only-admin-pw`

Die Zugangsdaten sind reine Entwicklungswerte aus `docker-compose.yaml`.
Builtin-Authentifizierung ist aktiviert. Der initiale Admin wird nur beim ersten
Start des Datenvolumes angelegt.

## Workflows und Daten

Lokal ist `dagu/workflows/` schreibbar nach `/var/lib/dagu/dags` eingebunden.
Änderungen aus Repository oder UI betreffen daher dieselben Dateien. Laufdaten,
Logs und Wiki liegen getrennt im Docker-Volume `dagu-data`.

In Produktion werden die DAGs direkt aus dem Repository-Pfad
`/opt/modeling-copilot/dagu/workflows` auf dem K3s-Node schreibgeschützt unter
`/app/workflows` eingebunden. Die Basiskonfiguration wird entsprechend aus
`/opt/modeling-copilot/dagu/infra/base.yaml` bereitgestellt. Laufdaten, Logs,
Wiki und das primäre DAG-Verzeichnis liegen auf dem PVC `dagu-data`.

## Produktion (K3s/Portainer)

Das Manifest `infra/prod/k3s-dagu.yaml` stellt folgende Ressourcen bereit:

- Namespaces `dagu` und `workflow-runtime`
- Service Accounts und namespaced RBAC für Kubernetes Jobs und Pod-Logs
- Dagu Deployment, 5-GiB-PVC und ClusterIP-Service
- Traefik-Ingress unter `https://ikarus.mni.thm.de/dagu`

Vor dem Deployment muss das Repository auf dem K3s-Node unter
`/opt/modeling-copilot` ausgecheckt sein. Bei einem anderen Checkout-Pfad sind
die beiden `hostPath.path`-Werte im Deployment anzupassen. ConfigMaps für die
Workflows und `base.yaml` sind nicht erforderlich.

Zusätzlich wird im Namespace `dagu` folgendes Objekt erwartet:

- Secret `dagu-auth` mit den Keys `token-secret`, `admin-username` und
  `admin-password`

Deployment:

```bash
kubectl apply -f dagu/infra/prod/k3s-dagu.yaml
```

Produktive Zugangsdaten werden ausschließlich über das Secret `dagu-auth`
bereitgestellt.
