---
---
# Day 22 — Exercises

## Exercise 1 — Write the minimal CRD and instance from scratch
Without looking at `crd-minimal.yaml`, write a CustomResourceDefinition registering a `Widget` kind (plural `widgets`, group `scratch.zero2hero.dev`), with `x-kubernetes-preserve-unknown-fields: true` and no other validation. Apply it, then create a `Widget` instance named `scratch-widget` with any field you like under `spec`. Confirm `kubectl get widgets` and `kubectl get widget scratch-widget -o yaml` both work exactly like a built-in type. Delete both afterward.

[→ solution](SOLUTIONS.md#exercise-1)

## Exercise 2 — Schema validation rejects bad data
Try `kubectl apply -f -` with a `Website` object setting `spec.replicas: 50` (above the CRD's `maximum: 10`) and another with `spec.replicas: "four"` (a string, not an integer). Record both exact rejection messages. What component rejected these — the mini-operator, or something else entirely? What does this prove about where `openAPIV3Schema` validation happens in the request pipeline (tie back to Day 17's admission pipeline diagram)?

[→ solution](SOLUTIONS.md#exercise-2)

## Exercise 3 — Owner references and garbage collection
With the mini-operator running and `marketing-site` reconciled, delete the `Website` object: `kubectl delete website marketing-site`. Does `deployment/website-marketing-site` get deleted automatically, even though the mini-operator never explicitly deleted it? Explain this using the `ownerReferences` block in `mini-operator.sh`'s generated Deployment — connect it to Day 4 Exercise 1's `--cascade=orphan` discussion.

[→ solution](SOLUTIONS.md#exercise-3)

## Exercise 4 — A CRD with no operator running
Stop the mini-operator (Ctrl-C or `kill`). Create a brand-new `Website` object, `abandoned-site`. Confirm `kubectl get website abandoned-site` shows it happily existing with `status.phase` never set (or stuck at its last value). What does this concretely demonstrate about the *decoupling* between an API object's existence and anything actually happening as a result of it — and why should a monitoring setup (Day 18) specifically alert on "operator Pod is down," not just "is the CRD's objects readable"?

[→ solution](SOLUTIONS.md#exercise-4)

## Exercise 5 — A third Kustomize overlay: staging
Create `overlays/staging/kustomization.yaml`, setting `namespace: staging`, `replicas: 2`, and a `GREETING=Hello from STAGING!` merge into the ConfigMap — without copying `base/`'s files at all (only reference them). Apply it into a new `staging` namespace and confirm it coexists correctly alongside `dev` and `prod`.

[→ solution](SOLUTIONS.md#exercise-5)

## Exercise 6 — commonLabels propagation
Run `kubectl get deployment -n dev hello-k8s -o jsonpath='{.metadata.labels}'`. Confirm the `managed-by: kustomize` label from `base/kustomization.yaml`'s `commonLabels` appears, even though neither `deployment.yaml` nor the dev overlay mentions it directly. Explain what `commonLabels` actually does across an entire kustomization tree, and name one practical use (hint: think about how you'd later select/audit "everything this Kustomize setup created," similar to how Helm's `app.kubernetes.io/instance` label worked on Day 19).

[→ solution](SOLUTIONS.md#exercise-6)

## Exercise 7 (stretch) — Convert the CRD's mini-operator logic into a Kustomize component
This is a conceptual exercise: explain, in a few sentences, why Kustomize is the **wrong tool** to build something like `mini-operator.sh`'s behavior (reacting live to a `Website` object's field changing and creating/updating other objects in response) even though Kustomize can generate Deployments/Services from structured input. What fundamental capability does an Operator's reconciliation loop have that a `kubectl apply -k` invocation — run once, by a human or CI pipeline — structurally cannot?

[→ solution](SOLUTIONS.md#exercise-7)
