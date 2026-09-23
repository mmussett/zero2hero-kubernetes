---
---
# Day 22 — Solutions

## Exercise 1
```yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: widgets.scratch.zero2hero.dev
spec:
  group: scratch.zero2hero.dev
  names:
    kind: Widget
    plural: widgets
  scope: Namespaced
  versions:
    - name: v1
      served: true
      storage: true
      schema:
        openAPIV3Schema:
          type: object
          x-kubernetes-preserve-unknown-fields: true
---
apiVersion: scratch.zero2hero.dev/v1
kind: Widget
metadata:
  name: scratch-widget
spec:
  color: blue
```
```bash
kubectl apply -f scratch-widget.yaml
kubectl get widgets
kubectl get widget scratch-widget -o yaml   # spec.color: blue, stored and returned faithfully
kubectl delete -f scratch-widget.yaml
```
The CRD's `metadata.name` had to be exactly `<plural>.<group>` (`widgets.scratch.zero2hero.dev`) — getting that wrong is the single most common CRD-authoring mistake, and the API server rejects it immediately if it doesn't match `spec.names.plural` + `spec.group`.

## Exercise 2
```bash
kubectl apply -f - <<'EOF'
apiVersion: training.zero2hero.dev/v1alpha1
kind: Website
metadata: {name: too-many}
spec: {greeting: "hi", replicas: 50}
EOF
# The Website "too-many" is invalid: spec.replicas: Invalid value: 50: spec.replicas in body should be less than or equal to 10
kubectl apply -f - <<'EOF'
apiVersion: training.zero2hero.dev/v1alpha1
kind: Website
metadata: {name: bad-type}
spec: {greeting: "hi", replicas: "four"}
EOF
# The Website "bad-type" is invalid: spec.replicas: Invalid type: string, expected: integer
```
Both are rejected by **`kube-apiserver` itself**, specifically its built-in **schema validation** stage — the exact same stage in Day 17's admission pipeline diagram that sits *before* validating admission webhooks/policies even run, and long before any controller (or, here, the mini-operator) ever sees the object. The mini-operator never gets a chance to run at all in either case; these objects are never persisted to etcd. This proves the `openAPIV3Schema` in a CRD gives you real, server-side input validation "for free," identical in guarantee strength to the schema validation built-in types like `Pod` already get — no controller code has to defensively re-check "is replicas actually a sane integer" itself.

## Exercise 3
```bash
kubectl delete website marketing-site
sleep 2
kubectl get deployment website-marketing-site
# Error from server (NotFound) — deleted automatically
```
Yes — it's deleted automatically, entirely by Kubernetes's built-in **garbage collection**, not by any code the mini-operator wrote to handle deletion. `mini-operator.sh` set `ownerReferences` on the generated Deployment pointing back at the `Website` object (with `controller: true`), which is the exact same mechanism Day 4 Exercise 1 explored for Deployment→ReplicaSet ownership — when an owner object is deleted, Kubernetes's garbage collector automatically cascades deletion to every dependent object referencing it via `ownerReferences`, unless that deletion is explicitly done with `--cascade=orphan`. This is a critical, easy-to-miss lesson for anyone writing a real operator: **setting ownerReferences correctly gets you free, correct cleanup on deletion** — forgetting it is one of the most common real-world operator bugs, leaving orphaned resources behind indefinitely after their owning custom resource is gone.

## Exercise 4
```bash
kill %1   # stop mini-operator.sh
kubectl apply -f - <<'EOF'
apiVersion: training.zero2hero.dev/v1alpha1
kind: Website
metadata: {name: abandoned-site}
spec: {greeting: "nobody is watching me", replicas: 3}
EOF
kubectl get website abandoned-site -o yaml | grep -A2 status
# status: {}  — never populated, no Deployment/Service ever created
```
This concretely demonstrates that a CRD is purely a **data storage and validation contract** with the API server — the object's continued existence and correctness is entirely decoupled from anything actually *acting* on it; `kubectl get` happily reports the object exists and is schema-valid regardless of whether any controller/operator process is even running. A monitoring setup should specifically alert on "operator Pod is down/unhealthy" (a liveness/readiness signal on the controller workload itself, Day 3) rather than only checking "can I read Website objects from the API" — the latter check would report perfectly healthy even in a total outage of the actual automation, since reading/writing the CR data plane and running the control-plane logic that reacts to it are two independent systems that can fail completely independently of each other.

## Exercise 5
```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: staging
resources:
  - ../../base
configMapGenerator:
  - name: hello-config
    behavior: merge
    literals:
      - GREETING=Hello from STAGING!
replicas:
  - name: hello-k8s
    count: 2
```
```bash
mkdir -p overlays/staging
# (save the above as overlays/staging/kustomization.yaml)
kubectl create namespace staging
kubectl apply -k overlays/staging/
kubectl get deployment -n staging hello-k8s -o jsonpath='{.spec.replicas}'; echo   # 2
```
All three overlays (`dev`, `prod`, `staging`) reference the identical `../../base` — none duplicate `deployment.yaml`/`service.yaml` at all, proving the base truly is reused, not copy-pasted, across every environment.

## Exercise 6
```bash
kubectl get deployment -n dev hello-k8s -o jsonpath='{.metadata.labels}'; echo
# {"app":"hello-k8s","managed-by":"kustomize"}
```
`commonLabels` in `base/kustomization.yaml` injects that label pair onto **every** resource the kustomization produces (and, per Kustomize's default behavior, also into matching `selector`/`matchLabels` fields automatically, keeping everything internally consistent) — every overlay building on this base inherits it transparently, with zero repetition in the overlay files themselves. Practically, this is exactly what lets you run `kubectl get all -l managed-by=kustomize -A` to audit or bulk-inspect **every single object this entire Kustomize tree created across every namespace/overlay** in one command — precisely analogous to how Day 19's Helm-injected `app.kubernetes.io/instance` label let you select all objects belonging to one release.

## Exercise 7
Kustomize is fundamentally a **static rendering/patching tool**: `kubectl apply -k` runs exactly once, transforms YAML on your local machine (or CI runner) at that single moment, sends the result to the API server, and then Kustomize itself is completely finished and gone — it has no running process, no persistent connection to the cluster, and no way to be notified later that anything changed. An Operator's entire value is the opposite: it is a **long-running, continuously watching process** that reacts to changes **at any future point**, indefinitely, with no human or CI pipeline needing to re-trigger anything — exactly the reconciliation loop from Day 2's architecture diagram. Kustomize could, in principle, be used *by* a human or a CI/CD pipeline to *generate* the YAML an operator would apply once at deploy time — but it structurally cannot replace the operator's job of noticing, on its own, days later, that someone edited a `Website` object's `replicas` field via `kubectl patch` and reacting automatically, because nothing about Kustomize is ever running in the cluster to notice that event at all.
