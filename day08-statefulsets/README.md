# Day 8 — StatefulSets & Stable Network Identity

## Learning objectives
- Explain what problem StatefulSets solve that Deployments cannot
- Understand stable, predictable Pod naming and per-Pod persistent storage
- Use a headless Service for direct per-Pod DNS addressing
- Observe StatefulSets' ordered, sequential creation/deletion guarantees
- Know when to reach for a StatefulSet vs. a Deployment

## 1. Concepts

### 1.1 Anatomy of a minimal StatefulSet

`statefulset-minimal.yaml` is the smallest valid StatefulSet — no storage, no init containers:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: hello-world
spec:
  clusterIP: None       # headless — REQUIRED for a StatefulSet, not optional (§1.2 point 2)
  selector:
    app: hello-world
  ports:
    - port: 8080
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: hello-world
spec:
  serviceName: hello-world     # names the headless Service above — this link is mandatory
  replicas: 2
  selector:
    matchLabels:
      app: hello-world
  template:
    metadata:
      labels:
        app: hello-world
    spec:
      containers:
        - name: hello-world
          image: localhost:5000/hello-k8s:1.0.0
```

Compared to Day 4's minimal Deployment, exactly two things are different: `serviceName` (pointing at a headless Service that must already exist or be created alongside it) and the word `StatefulSet` itself — everything else (`selector`, `template`) is identical in shape. `volumeClaimTemplates` is genuinely optional; without it you still get stable naming and stable network identity (§1.2's guarantees 1 and 2), just not guarantee 3 (per-replica storage) — this file proves those two guarantees don't actually require persistent storage to exist at all.

### 1.2 What Deployments get wrong for stateful workloads

A Deployment's Pods are interchangeable — they get random name suffixes (`hello-k8s-7d9f8c-x2k4p`), random IPs, and a fresh (or shared dynamically-provisioned) volume with no guaranteed relationship to *which* replica it was before. That's exactly right for stateless web servers, and exactly wrong for a clustered database, a Kafka broker, or anything where **each replica has a distinct identity and its own durable data** that must reattach to that same identity after a restart.

[**StatefulSet**](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/) gives you three guarantees Deployments don't:

1. **Stable, predictable Pod names** — `<statefulset-name>-0`, `-1`, `-2`, ... never random suffixes. If `hello-stateful-1` dies, its replacement is named `hello-stateful-1` again, not something new.
2. **Stable network identity via a [headless Service](https://kubernetes.io/docs/concepts/services-networking/service/#headless-services)** — each Pod gets its own DNS record, `<pod-name>.<service-name>.<namespace>.svc.cluster.local`, so you can address `hello-stateful-0` specifically instead of hitting "whichever replica the Service load-balances to" (recall Day 5's headless Service preview).
3. **Stable, per-replica storage via `volumeClaimTemplates`** — instead of one shared PVC, each replica gets its **own** PVC, created automatically, named after it (`data-hello-stateful-0`, etc.), and critically — **that same PVC re-attaches to the replacement Pod** if `hello-stateful-1` is deleted and recreated. Data follows identity.

### 1.3 [Ordering guarantees](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/#pod-management-policies)

By default (`podManagementPolicy: OrderedReady`), a StatefulSet creates Pods **one at a time, in order** (`-0` must be `Running and Ready` before `-1` starts), and deletes them in **strict reverse order** (`-2` before `-1` before `-0`) during scale-down. This matters for workloads with startup dependencies (a replica joining a cluster needs a primary already up) or ordered shutdown requirements. `podManagementPolicy: Parallel` opts out of this when you don't need it, for faster scaling.

### 1.4 When to use which

| | Deployment | StatefulSet |
|---|---|---|
| Pod identity | Interchangeable | Unique, stable, numbered |
| Storage | Usually shared or none; if per-Pod storage is needed it's awkward | One PVC per replica, automatic, re-attaches correctly |
| Networking | Load-balanced via Service, any replica is fine | Individually addressable via headless Service |
| Scaling order | Any order, any speed | Sequential by default |
| Typical workloads | Stateless web/API servers, workers | Databases (Postgres, MySQL, MongoDB, Cassandra), message brokers (Kafka, RabbitMQ clustering), anything with leader/follower topology |

**Important nuance:** a StatefulSet alone does **not** give you replication, quorum, or leader election — it only gives stable identity and storage. Actually running a correctly clustered database still requires that database's own clustering logic (often via an [Operator](../day22-crds-operators-and-kustomize/README.md), Day 22) built on top of what a StatefulSet provides.

### Official documentation
- [StatefulSets](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/)
- [StatefulSet Basics (tutorial)](https://kubernetes.io/docs/tutorials/stateful-application/basic-stateful-set/)
- [Headless Services](https://kubernetes.io/docs/concepts/services-networking/service/#headless-services)
- [Running a Replicated Stateful Application](https://kubernetes.io/docs/tasks/run-application/run-replicated-stateful-application/)
- [StatefulSet: Pod Identity](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/#pod-identity)

## 2. Hands-on lab

```bash
cd day08-statefulsets/manifests

# 2.1 The absolute minimum
kubectl apply -f statefulset-minimal.yaml
kubectl get pods -l app=hello-world -w    # ctrl-c once both are Running — note the -0/-1 naming
kubectl exec hello-world-0 -- curl -s localhost:8080/
kubectl delete -f statefulset-minimal.yaml

# 2.2 Deploy and watch strictly sequential creation
kubectl apply -f headless-service.yaml
kubectl apply -f statefulset.yaml
kubectl get pods -l app=hello-stateful -w
# note: -0 reaches Running/Ready BEFORE -1 is even created, and so on

# 2.3 Confirm stable naming and per-Pod storage
kubectl get pods -l app=hello-stateful
kubectl get pvc
# data-hello-stateful-0, data-hello-stateful-1, data-hello-stateful-2 — one each

# 2.4 Individually addressable DNS
kubectl run netshoot --rm -it --image=nicolaka/netshoot --restart=Never -- \
  sh -c "nslookup hello-stateful-1.hello-stateful.default.svc.cluster.local"

# 2.5 Prove identity + storage survive Pod deletion
kubectl exec hello-stateful-1 -- cat /data/identity.txt
kubectl delete pod hello-stateful-1
kubectl get pods -l app=hello-stateful -w   # replacement is named hello-stateful-1 again
kubectl exec hello-stateful-1 -- cat /data/identity.txt   # SAME content — same PVC re-attached

# 2.6 Scale down and observe reverse-order, and that PVCs are NOT deleted
kubectl scale statefulset hello-stateful --replicas=1
kubectl get pods -l app=hello-stateful -w    # -2 terminates first, then -1
kubectl get pvc    # all three PVCs still exist! StatefulSets never auto-delete PVCs

# 2.7 Scale back up — does data-hello-stateful-1 get its old data back?
kubectl scale statefulset hello-stateful --replicas=3
kubectl exec hello-stateful-1 -- cat /data/identity.txt   # yes — same PVC, same data

# 2.8 Clean up (PVCs must be deleted separately — this is intentional, see Exercise 2)
kubectl delete -f statefulset.yaml -f headless-service.yaml
kubectl delete pvc -l app=hello-stateful
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `-1` never starts, stuck behind `-0` | `podManagementPolicy: OrderedReady` (the default) strictly requires `-0` to be `Running and Ready` before `-1` is even created | Fix whatever is blocking `-0` first (probes, image, PVC) — `-1` won't move until it's resolved, by design |
| Deleted a Pod, but its replacement doesn't reuse the old data | You deleted the **PVC** too (or the whole StatefulSet with a cascading delete), not just the Pod | Only `kubectl delete pod <ordinal-name>` if you want to keep its storage — the StatefulSet controller recreates the Pod with the *same* PVC automatically |
| Scaled down, then back up — replica's data is empty/different | PVCs from scaled-down ordinals are retained by default (never auto-deleted), but confirm you scaled back up to the *same* ordinal count, not created a differently-named replacement | `kubectl get pvc` — the old PVC should still be there and get reattached to the same ordinal when it returns |
| `nslookup <pod-name>.<service-name>` fails from inside the cluster | The headless Service (`clusterIP: None`) doesn't exist, or its name doesn't match `spec.serviceName` on the StatefulSet | `kubectl get svc <service-name> -o jsonpath='{.spec.clusterIP}'` should print nothing/`None`; confirm the StatefulSet's `serviceName` field matches exactly |
| StatefulSet Pods run fine, but peers still can't find each other by name | Same as above — Pods can be `Running` and healthy even with a broken/missing headless Service; nothing checks this at admission time | Explicitly verify the headless Service exists before assuming clustering logic itself is broken |

See also: [Debugging Common Kubernetes Issues](../TROUBLESHOOTING.md).

## 3. Key commands reference

| Command | Purpose |
|---|---|
| `kubectl get statefulset` (`sts`) | List StatefulSets |
| `kubectl scale statefulset <name> --replicas=N` | Scale (sequential order still applies) |
| `kubectl get pvc -l app=<label>` | List the per-replica PVCs a StatefulSet created |
| `kubectl delete pod <sts-name>-N` | Delete one specific ordinal — its replacement reuses the same name and PVC |

Next: [Day 9 — DaemonSets, Jobs & CronJobs](../day09-daemonsets-jobs-cronjobs/README.md)
