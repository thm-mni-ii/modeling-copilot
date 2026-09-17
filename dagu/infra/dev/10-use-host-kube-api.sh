#!/bin/sh
set -eu

mkdir -p /etc/kube

# Docker Desktop's host kubeconfig uses a loopback API endpoint. In a
# container, loopback refers to that container, so use Docker's host alias
# without changing the developer's kubeconfig on the host. TLS still verifies
# the certificate's localhost name.
sed \
  -e 's#\(https\?://\)\(127\.0\.0\.1\|localhost\)#\1host.docker.internal#g' \
  -e '/^[[:space:]]*server:[[:space:]]*https:\/\/host\.docker\.internal/ a\
    tls-server-name: localhost' \
  /etc/kube/source-config > /etc/kube/config
