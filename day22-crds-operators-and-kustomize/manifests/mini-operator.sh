#!/usr/bin/env bash
# A "mini operator" in ~30 lines of bash — a deliberately minimal, readable
# stand-in for what tools like the Operator SDK / kubebuilder generate as
# full Go programs. This is NOT how you'd build a real operator (a real one
# uses a proper watch-based informer, not polling, and handles errors,
# retries, and finalizers) — it exists purely to make the reconciliation
# LOOP concept from Day 2 concrete and inspectable, for one custom resource.
#
# For every Website object, this script ensures a matching Deployment +
# Service exist with the right image/greeting/replica count, and writes
# back a status. Run it in the foreground and watch it react live.
set -euo pipefail

echo "mini-operator watching 'websites.training.zero2hero.dev' — Ctrl-C to stop"

while true; do
  for name in $(kubectl get websites -o jsonpath='{.items[*].metadata.name}' 2>/dev/null); do
    greeting=$(kubectl get website "$name" -o jsonpath='{.spec.greeting}')
    replicas=$(kubectl get website "$name" -o jsonpath='{.spec.replicas}')

    echo "[reconcile] Website/$name -> replicas=$replicas greeting=\"$greeting\""

    cat <<EOF | kubectl apply -f - >/dev/null
apiVersion: apps/v1
kind: Deployment
metadata:
  name: website-${name}
  labels: {managed-by: mini-operator, website: ${name}}
  ownerReferences:
    - apiVersion: training.zero2hero.dev/v1alpha1
      kind: Website
      name: ${name}
      uid: $(kubectl get website "$name" -o jsonpath='{.metadata.uid}')
      controller: true
spec:
  replicas: ${replicas}
  selector: {matchLabels: {website: ${name}}}
  template:
    metadata: {labels: {website: ${name}}}
    spec:
      containers:
        - name: hello-k8s
          image: localhost:5000/hello-k8s:1.0.0
          env: [{name: GREETING, value: "${greeting}"}]
          ports: [{containerPort: 8080}]
---
apiVersion: v1
kind: Service
metadata:
  name: website-${name}
  labels: {managed-by: mini-operator, website: ${name}}
spec:
  selector: {website: ${name}}
  ports: [{port: 80, targetPort: 8080}]
EOF

    kubectl patch website "$name" --type merge --subresource status \
      -p "{\"status\":{\"phase\":\"Reconciled\",\"observedReplicas\":${replicas}}}" >/dev/null
  done
  sleep 5
done
