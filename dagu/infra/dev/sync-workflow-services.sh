#!/bin/sh
# Runs on every `docker compose up`; never deletes workflow data or cluster resources.
set -eu
cd /workspace
node=desktop-control-plane
services="workflow-data workflow-graph-parser workflow-model-label-extraction workflow-synonym-matching workflow-one-to-one-matching workflow-analytical-feedback workflow-feedback-generation"
kube() {
  docker exec "$node" kubectl --kubeconfig /etc/kubernetes/admin.conf "$@"
}
docker inspect "$node" >/dev/null
# The mount is read-only. Build contexts are sent to the host daemon by Compose.
images=""
for service in $services; do
  image=$(docker compose --profile workflow-services config --images "$service")
  folder=${image#modeling-copilot/}
  folder=${folder%:*}
  key=$(printf '%s' "$image" | tr '/:' '__')
  fingerprint=$(find "dagu/workflow-services/$folder" -type f ! -path '*/__pycache__/*' ! -name '*.pyc' -print | sort | xargs sha256sum; sha256sum dagu/workflow-services/*.py; cat "dagu/workflow-services/$folder/Dockerfile")
  # Feedback also copies the shared analytical contract into its image.
  if [ "$folder" = feedback-generation ]; then
    fingerprint="$fingerprint $(sha256sum dagu/workflow-services/analytical-feedback/src/analysis_contract.py)"
  fi
  fingerprint=$(printf '%s' "$fingerprint" | sha256sum | cut -d ' ' -f 1)
  if ! docker image inspect "$image" >/dev/null 2>&1 || { [ -f "/state/$key.source" ] && [ "$(cat "/state/$key.source")" != "$fingerprint" ]; }; then
    docker compose --profile workflow-services build "$service"
  fi
  # Existing versioned images are the initial baseline; code changes must bump tags.
  printf '%s' "$fingerprint" > "/state/$key.pending"
  images="$images $image"
done
changed=""
for image in $images; do
  digest=$(docker image inspect --format '{{.Id}}' "$image")
  cached=$(docker exec "$node" ctr -n k8s.io images list -q | grep -Fx "docker.io/$image" || true)
  key=$(printf '%s' "$image" | tr '/:' '__')
  if [ -z "$cached" ] || [ "$(cat "/state/$key" 2>/dev/null || true)" != "$digest" ]; then
    echo "Importing $image into Kubernetes"
    # A file avoids masking docker-save failures and keeps the image stream binary.
    docker image save -o /state/image.tar "$image"
    docker exec -i "$node" ctr -n k8s.io images import - < /state/image.tar
    rm /state/image.tar
    printf '%s' "$digest" > "/state/$key.pending-digest"
    changed="$changed ${image#modeling-copilot/}"
  fi
done
docker exec -i "$node" kubectl --kubeconfig /etc/kubernetes/admin.conf apply -f - < dagu/infra/dev/kubernetes.yaml
docker exec -i "$node" kubectl --kubeconfig /etc/kubernetes/admin.conf apply -f - < dagu/infra/workflow-services.yaml
# Also cover rebuilt local images whose tag was accidentally left unchanged.
for image in $changed; do
  kube -n workflow-runtime rollout restart "deployment/${image%:*}"
done
for deployment in workflow-data graph-parser model-label-extraction synonym-matching one-to-one-graph-matching analytical-feedback feedback-generation; do
  kube -n workflow-runtime rollout status "deployment/$deployment" --timeout=180s
done
for image in $images; do
  key=$(printf '%s' "$image" | tr '/:' '__')
  mv "/state/$key.pending" "/state/$key.source"
  if [ -f "/state/$key.pending-digest" ]; then
    mv "/state/$key.pending-digest" "/state/$key"
  fi
done
echo "Workflow services synchronized."
