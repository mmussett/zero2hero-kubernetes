# Day 22 — Custom Resources, Operators & Kustomize

## Learning objectives
- Extend the Kubernetes API with your own resource type via a CustomResourceDefinition (CRD)
- Explain the Operator pattern as "a reconciliation loop for a resource type you invented"
- Watch a minimal hand-written controller reconcile a custom resource live
- Use Kustomize to manage dev/prod variants of the same manifests without templating or duplication
- Understand where Kustomize and Helm (Day 19) overlap and where they differ

## 1. Concepts

### 1.1 Anatomy of a minimal CustomResourceDefinition

`crd-minimal.yaml` is about as small as a CRD gets:

```yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: helloworlds.training.zero2hero.dev   # MUST be <plural>.<group>
spec:
  group: training.zero2hero.dev                # the API group your new type lives under
  names:
    kind: HelloWorld                             # what you'll write in kind: on instances
    plural: helloworlds                           # what `kubectl get` uses
  scope: Namespaced
  versions:
    - name: v1
      served: true
      storage: true
      schema:
        openAPIV3Schema:
          type: object
          x-kubernetes-preserve-unknown-fields: true   # NO validation at all — accept any fields under spec
```

A working instance needs almost nothing either:

```yaml
apiVersion: training.zero2hero.dev/v1
kind: HelloWorld
metadata:
  name: hello-world
spec:
  message: "Hello, minimal world!"
```

`schema.openAPIV3Schema` is the one field you genuinely can't omit, even at the minimum — every CRD needs *some* schema, even if (as here) it's the loosest possible one, accepting arbitrary fields with zero validation. `crd-website.yaml` (used later this day) adds real per-field validation — required fields, `minimum`/`maximum`, printer columns, a `status` subresource — on top of this exact same shape; none of that richness is required to get a working custom type.

### 1.2 CustomResourceDefinition — teaching the API server new nouns

Everything since Day 3 has used resource types Kubernetes ships with (`Pod`, `Deployment`, `Service`...). A [**CustomResourceDefinition (CRD)**](https://kubernetes.io/docs/concepts/extend-kubernetes/api-extension/custom-resources/) registers an entirely new resource *type* with `kube-apiserver` — after applying one, `kubectl get <your-new-kind>`, `kubectl describe`, `kubectl apply -f`, RBAC rules (Day 16), and even `kubectl explain` **all work exactly like they do for built-in types**, because the API server treats CRD-defined resources identically to native ones once registered — full CRUD, storage in etcd, `openAPIV3Schema` validation, everything. You already used a CRD without necessarily naming it as such: Day 11's Traefik `Middleware` and Day 17's `ValidatingAdmissionPolicy` are exactly this mechanism, whether shipped by a third party or by Kubernetes itself.

**Critically: a CRD by itself does nothing except let you store and retrieve structured data.** `kubectl apply -f website-instances.yaml` today will succeed and the objects will sit in etcd — but nothing will *act* on them until something is watching.

### 1.3 The Operator pattern — a reconciliation loop for your CRD

Recall Day 2's core idea: every built-in controller (Deployment controller, ReplicaSet controller...) follows the same loop — **watch for objects, compare desired state to actual state, act to close the gap, repeat forever.** An [**Operator**](https://kubernetes.io/docs/concepts/extend-kubernetes/operator/) is exactly that same pattern, written by *you* (or a vendor), for a CRD *you* (or they) defined. It encodes operational knowledge as code: "when someone creates a `Website` object requesting 2 replicas and this greeting, here's exactly what Kubernetes objects need to exist, and how to keep them in sync if the `Website` object changes."

This is why Operators are how most complex stateful systems (databases, message brokers) are run on Kubernetes in practice: a human's mental checklist for "how do I safely add a replica to this Postgres cluster, resync it, and update the primary's config" gets encoded once as an Operator's reconciliation logic, then anyone can trigger that entire safe procedure by editing one custom resource field.

Today's `mini-operator.sh` is a **deliberately minimal, readable stand-in** for what a real Operator does — polling instead of a proper watch stream, no error handling or retries, no finalizers — built specifically so the reconciliation loop is inspectable in ~30 lines of bash rather than buried in generated Go. Real Operators are typically built with frameworks like [kubebuilder](https://book.kubebuilder.io/) or the [Operator SDK](https://sdk.operatorframework.io/), and many mature ones are published for direct reuse on [OperatorHub](https://operatorhub.io/) — you rarely need to write one from scratch for popular software.

### 1.4 Kustomize — template-free environment variants

[**Kustomize**](https://kubectl.kubernetes.io/) (built directly into `kubectl` via `kubectl apply -k`) solves a similar problem to part of what Helm (Day 19) solves — managing dev/staging/prod variants of the same application — but with a fundamentally different philosophy: **no templating language at all.** You write a `base/` of plain, valid, complete Kubernetes YAML, and each environment's `overlays/<env>/kustomization.yaml` declares **patches, generators, and settings that transform the base** — never a `{{ }}` expression anywhere.

Key Kustomize mechanisms used in this lab's `overlays/`:
- `resources:` — pull in the base (or other kustomizations).
- `namespace:` — set/override the target namespace for every resource, cluster-wide within this overlay.
- `replicas:` — override a Deployment's replica count without a full patch.
- `patches:` (JSON Patch or strategic merge) — surgically change specific fields (today: CPU requests/limits) without repeating the whole manifest.
- `configMapGenerator` with `behavior: merge` — layer additional key/value pairs onto a ConfigMap the base already generates, and auto-append a content hash to its name (this is *why* Kustomize-generated ConfigMaps trigger a rolling update on change, unlike a hand-written ConfigMap referenced by a fixed name, which Day 6 showed doesn't restart Pods automatically).

### 1.5 Kustomize vs. Helm — when to reach for which

| | Kustomize | Helm |
|---|---|---|
| Templating | None — pure YAML + structured patches | Full templating language (Go templates + Sprig) |
| Distribution | No packaging concept — just directories, usually version-controlled directly alongside your app | Versioned, packaged, shareable charts (Artifact Hub) |
| Best fit | Your own app's environment variants, where you own and read every line of YAML | Installing complex third-party software (Day 18's Prometheus stack) with many conditional/parameterized options you don't want to hand-write |
| Learning curve | Low — if you can read YAML, you can read a Kustomize overlay | Higher — templating logic can obscure the final rendered output |

Many real teams use **both**: Helm to install third-party infrastructure components, Kustomize (or Helm itself, or plain `kubectl apply -k` in CI) to manage their own application's environment-specific config on top.

### Official documentation
- [Custom Resources](https://kubernetes.io/docs/concepts/extend-kubernetes/api-extension/custom-resources/)
- [Extend the Kubernetes API with CustomResourceDefinitions (tutorial)](https://kubernetes.io/docs/tasks/extend-kubernetes/custom-resources/custom-resource-definitions/)
- [Operator pattern](https://kubernetes.io/docs/concepts/extend-kubernetes/operator/)
- [kubebuilder book](https://book.kubebuilder.io/)
- [OperatorHub.io](https://operatorhub.io/)
- [Kustomize documentation](https://kubectl.kubernetes.io/references/kustomize/)
- [Kustomize: Declarative Management of Kubernetes Objects](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/)

## 2. Hands-on lab

```bash
cd day22-crds-operators-and-kustomize/manifests

# 2.1 The absolute minimum
kubectl apply -f crd-minimal.yaml
kubectl apply -f helloworld-minimal.yaml
kubectl get helloworlds                        # works exactly like `kubectl get pods`
kubectl get helloworld hello-world -o yaml       # your custom fields, stored and returned faithfully
kubectl delete -f helloworld-minimal.yaml -f crd-minimal.yaml

# 2.2 Register the (real, validated) CRD, prove it behaves like any built-in type
kubectl apply -f crd-website.yaml
kubectl get crd websites.training.zero2hero.dev
kubectl explain website.spec        # yes — works exactly like `kubectl explain pod.spec`
kubectl api-resources | grep website

# 2.3 Create instances — stored, but nothing acts on them yet
kubectl apply -f website-instances.yaml
kubectl get websites
kubectl get deployments   # nothing was created — the CRD alone does nothing

# 2.4 Run the mini-operator and watch it reconcile, live
chmod +x mini-operator.sh
./mini-operator.sh &
sleep 6
kubectl get deployments -l managed-by=mini-operator
kubectl get website marketing-site -o yaml | grep -A2 status

# 2.5 Change desired state and watch reconciliation happen automatically
kubectl patch website marketing-site --type merge -p '{"spec":{"replicas":4}}'
sleep 6
kubectl get pods -l website=marketing-site   # now 4, no manual kubectl scale needed

kubectl patch website marketing-site --type merge -p '{"spec":{"greeting":"Updated via the operator!"}}'
sleep 6
kubectl rollout restart deployment website-marketing-site   # env var change still needs a restart, same as Day 6
kubectl exec deploy/website-marketing-site -- printenv GREETING

kill %1   # stop the mini-operator
kubectl delete -f website-instances.yaml -f crd-website.yaml

# 2.6 Kustomize: render without applying
cd ../kustomize
kubectl kustomize overlays/dev/ | less
kubectl kustomize overlays/prod/ | less
diff <(kubectl kustomize overlays/dev/) <(kubectl kustomize overlays/prod/)

# 2.7 Apply both overlays into separate namespaces
kubectl create namespace dev
kubectl create namespace prod
kubectl apply -k overlays/dev/
kubectl apply -k overlays/prod/
kubectl get deployment -n dev hello-k8s -o jsonpath='{.spec.replicas}'; echo    # 1
kubectl get deployment -n prod hello-k8s -o jsonpath='{.spec.replicas}'; echo   # 4
kubectl get configmap -n dev    # note the hash suffix on the generated ConfigMap name

# 2.8 Clean up
kubectl delete -k overlays/dev/
kubectl delete -k overlays/prod/
kubectl delete namespace dev prod
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `kubectl apply` on a custom resource fails with a schema validation error | The CRD's `openAPIV3Schema` rejected the value (wrong type, out of `min`/`max` range) — this is the CRD doing its job, not a bug | Read the exact error (it names the offending field) and fix the value; this happens entirely at the API server, before any controller sees it |
| Custom resource creates successfully, but nothing ever happens | No controller/operator is actually watching it — a CRD alone is just schema + storage, never automatic behavior (Day 22 §1.1's key lesson) | Confirm your operator/controller process (e.g. `mini-operator.sh`) is actually running |
| Deleted a custom resource, but the Deployment/Service it created is still there | The generated objects were never given `ownerReferences` pointing back at the custom resource | Add `ownerReferences` in the controller's generated manifests so Kubernetes garbage-collects dependents automatically |
| `kubectl apply -k <overlay>` fails with a patch error | JSON Patch `path` doesn't exist in the base resource at that exact location (often an off-by-one array index, or a field that doesn't exist yet) | `kubectl kustomize <overlay>` first to render and inspect the output before applying — always safe, no cluster contact |
| Kustomize-generated ConfigMap's Pods didn't restart after a values change | You edited a resource that ISN'T using `configMapGenerator` (so no content-hash suffix, hence no rollout trigger) — the hash-suffix mechanism is what wires this up (Day 22 §1.3) | Confirm the ConfigMap in question is actually declared under `configMapGenerator`, not just referenced as a plain, hand-written ConfigMap |

See also: [Debugging Common Kubernetes Issues](../TROUBLESHOOTING.md).

## 3. Key commands reference

| Command | Purpose |
|---|---|
| `kubectl get crd` | List registered CustomResourceDefinitions |
| `kubectl explain <custom-kind>.spec` | Field docs for a CRD, same as built-ins |
| `kubectl kustomize <dir>` | Render a kustomization to plain YAML, no cluster contact |
| `kubectl apply -k <dir>` / `kubectl delete -k <dir>` | Apply/delete a kustomization directly |
| `kubectl patch <kind> <name> --type merge -p '{...}' [--subresource status]` | Targeted field update, including status subresources |

Next: [Day 23 — Capstone Project](../day23-capstone-project/README.md)
