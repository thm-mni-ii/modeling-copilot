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

In Produktion holt ein Init-Container (`git-sync`) das öffentliche Repository
bei jedem Pod-Start per `git clone` in ein `emptyDir`-Volume. Der vollständige
Ordner `dagu/` wird unter `/app/dagu` eingebunden. Dagu liest die Workflows aus
`/app/dagu/workflows` und die Basiskonfiguration aus
`/app/dagu/infra/base.yaml`. Ein Host-seitiger Checkout ist nicht nötig, da
Portainer nur das Manifest anwendet. Laufdaten, Logs und Wiki liegen auf dem
PVC `dagu-data`.

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
