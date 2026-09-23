---
---
# Day 4 — ReplicaSets, Deployments, Rolling Updates & Rollbacks

## Learning objectives
- Write the smallest possible valid Deployment manifest from scratch, and explain why every line in it is required
- Read and write every commonly-used field in a Deployment spec — the ones that take you from "it runs" to "it's actually production-shaped"
- Explain the three-layer relationship: Deployment → ReplicaSet → Pod
- Perform a zero-downtime rolling update and understand `maxSurge`/`maxUnavailable`
- Roll back a bad deployment using revision history
- Scale a Deployment manually and understand self-healing
- Read `kubectl rollout status/history` output

## 1. Concepts

### 1.1 Anatomy of a Deployment manifest, field by field

Before the ownership chain, rolling updates, or rollback — the thing you'll actually type most often is the manifest itself. `deployment-minimal.yaml` is the smallest valid Deployment that exists; every field in it is **required**, and understanding why each one is required teaches you most of what a Deployment fundamentally is:

```yaml
apiVersion: apps/v1        # Deployments live in the "apps" API group, not the core "v1" group Pods use
kind: Deployment
metadata:
  name: hello-world         # the Deployment's OWN name — Pods it creates get a generated suffix, never this exact name
spec:
  replicas: 1                # desired Pod count — the whole point of a Deployment over a bare Pod (Day 3)
  selector:
    matchLabels:
      app: hello-world        # "these are MY Pods" — must match template.metadata.labels EXACTLY, or the API rejects this object
  template:                    # a full Pod spec, nested — literally the same shape as Day 3's Pod manifests
    metadata:
      labels:
        app: hello-world        # the label actually stamped onto every Pod this Deployment creates
    spec:
      containers:
        - name: hello-world       # container name within the Pod (matters for kubectl exec/logs -c, and for kubectl set image)
          image: localhost:5000/hello-k8s:1.0.0
```

Two things that trip up almost every beginner on their first hand-written Deployment:

1. **`spec.selector.matchLabels` and `spec.template.metadata.labels` must match.** The selector is how the Deployment (and its ReplicaSet, section 1.2) finds "which Pods belong to me" — if they don't match, `kubectl apply` fails validation immediately with an explicit error, before anything is even created.
2. **`spec.template` is a whole Pod spec, indented one level deeper.** If you already know how to write a Pod manifest (Day 3), you already know how to write 90% of a Deployment — you're not learning a new shape, you're wrapping the shape you already know in `replicas` + `selector`.

Once that minimum is running, here's the **complete map of the fields you'll actually use** in real Deployments — everything below is optional, added incrementally on top of the minimum, roughly in the order you'd reach for it:

| Field | What it does | Where it's taught |
|---|---|---|
| `spec.template.spec.containers[].ports` | **Purely informational/documentation** — it does *not* open or expose anything by itself. The container listens because the app itself binds that port; `ports` just lets `kubectl describe`/other tooling display it. A common beginner assumption ("I need `ports:` for the container to be reachable") is simply wrong | This day (`deployment-v1.yaml`); enforced/used for real by Services, Day 5 |
| `spec.template.spec.containers[].env` | Environment variables for the container — literal values or pulled from a ConfigMap/Secret | Day 3 (literal), Day 6 (ConfigMap/Secret) |
| `spec.template.spec.containers[].resources.requests`/`.limits` | What the scheduler reserves (`requests`) and the kernel enforces as a hard ceiling (`limits`) | Day 3, Day 10 |
| `spec.template.spec.containers[].readinessProbe`/`.livenessProbe`/`.startupProbe` | Whether a Pod is safe to send traffic to, and whether the kubelet should restart it | Day 3 |
| `spec.strategy.type` (`RollingUpdate`/`Recreate`) + `.rollingUpdate.maxSurge`/`.maxUnavailable` | How a rollout replaces old Pods with new ones | §1.3 below |
| `spec.revisionHistoryLimit` | How many old ReplicaSets are kept around for rollback (default 10) | §1.4 below |
| `spec.minReadySeconds` | How long a new Pod must stay Ready before it's considered available — a small buffer against a Pod that passes its readiness probe once, then immediately falls over | Mentioned here; rarely needed below its default of `0` |
| `spec.progressDeadlineSeconds` | How long the Deployment controller waits before marking a stalled rollout as `ProgressDeadlineExceeded` (default 600s) — this is *why* `kubectl rollout status` doesn't hang forever in real usage, even though our lab's short `--timeout` flags simulate the same idea faster | Referenced in this day's Troubleshooting section |
| `metadata.labels` **on the Deployment itself** | A completely separate set of labels from `spec.template.metadata.labels` — these label the *Deployment object*, not the Pods it creates. Easy to confuse; they serve different audiences (you organizing Deployments vs. Services selecting Pods) | This day's manifests set both, deliberately named the same, to make the distinction visible |

You don't need all of these on day one — `deployment-minimal.yaml` proves that. You add each one when you have an actual reason to (need a probe → add one; need to survive a Node dying with zero dropped requests → tune `maxSurge`/`maxUnavailable`), not because a checklist says so.

### 1.2 The ownership chain

```
Deployment  --owns-->  ReplicaSet  --owns-->  Pod(s)
 (you edit)             (auto-created,          (auto-created,
                          one per revision)        ephemeral)
```

- A [**ReplicaSet**](https://kubernetes.io/docs/concepts/workloads/controllers/replicaset/)'s only job is: "ensure exactly N Pods matching this label selector exist, always." If a Pod is deleted or its Node dies, the ReplicaSet's controller notices and creates a replacement — this is self-healing, and it's a completely separate mechanism from restarting a crashed container (that's the kubelet's job, within one Pod).
- A [**Deployment**](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/) manages ReplicaSets to give you rolling updates and rollback history. You almost never create a ReplicaSet directly — you write a Deployment and let it manage ReplicaSets for you. Each time you change the Pod template (e.g. bump the image), the Deployment creates a **new** ReplicaSet and gradually shifts replica count from the old one to the new one, deleting the old ReplicaSet's Pods as the new one becomes ready.

### 1.3 [Rolling update](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#rolling-update-deployment) knobs

- `maxUnavailable`: how many Pods below `replicas` are tolerated during the rollout (e.g. `0` = never drop below desired count — always surge instead).
- `maxSurge`: how many Pods **above** `replicas` are allowed temporarily.
- With `maxSurge: 1, maxUnavailable: 0` on `replicas: 3`, the rollout goes 3→4 (new Pod added and must become Ready)→3 (one old Pod removed), repeated — true zero-downtime as long as readiness probes are correct.

### 1.4 [Rollback](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#rolling-back-a-deployment)

Every revision of a Deployment's Pod template is kept in `ReplicaSet` history (bounded by [`spec.revisionHistoryLimit`](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#clean-up-policy), default 10). `kubectl rollout undo` simply scales the previous ReplicaSet back up and the current one down — it's the same rolling mechanism, in reverse.

### Official documentation
- [Deployments](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)
- [ReplicaSet](https://kubernetes.io/docs/concepts/workloads/controllers/replicaset/)
- [Deployment: Rolling Update strategy](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#rolling-update-deployment)
- [Deployment: Rolling Back a Deployment](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#rolling-back-a-deployment)
- [kubectl rollout Reference](https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands#rollout)

## 2. Hands-on lab

```bash
cd day04-deployments-replicasets/manifests

# 2.1 The absolute minimum — get this running before anything more complex
kubectl apply -f deployment-minimal.yaml
kubectl get deployment,replicaset,pod -l app=hello-world
kubectl exec deploy/hello-world -- curl -s localhost:8080/    # the app listens on 8080 even though we never wrote `ports:` anywhere
kubectl delete -f deployment-minimal.yaml

# 2.2 Create and observe the ownership chain (a more complete, realistic example)
kubectl apply -f deployment-v1.yaml
kubectl get deployment,replicaset,pod -l app=hello-k8s
kubectl describe deployment hello-k8s | head -20

# 2.3 Self-healing: delete a Pod and watch it come back
POD=$(kubectl get pod -l app=hello-k8s -o jsonpath='{.items[0].metadata.name}')
kubectl delete pod $POD
kubectl get pods -l app=hello-k8s -w    # ctrl-c once back to 3/3

# 2.4 Manual scaling
kubectl scale deployment hello-k8s --replicas=5
kubectl get pods -l app=hello-k8s
kubectl scale deployment hello-k8s --replicas=3

# 2.5 Rolling update
kubectl apply -f deployment-v2.yaml
kubectl rollout status deployment/hello-k8s
kubectl get replicaset -l app=hello-k8s     # two RS: old at 0, new at 3
kubectl rollout history deployment/hello-k8s

# 2.6 A bad rollout, and rolling it back
kubectl apply -f deployment-bad.yaml
kubectl rollout status deployment/hello-k8s --timeout=30s || true
kubectl get pods -l app=hello-k8s           # some ImagePullBackOff, but old Pods still serving
kubectl rollout undo deployment/hello-k8s
kubectl rollout status deployment/hello-k8s

# 2.7 Clean up
kubectl delete -f deployment-v1.yaml
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `kubectl apply` on a hand-written Deployment fails with a selector/label error | `spec.selector.matchLabels` doesn't exactly match `spec.template.metadata.labels` (§1.1) | Compare both blocks character-by-character — they must match exactly, including every key |
| Wrote `ports:` on the container but the app still isn't reachable from outside | `ports` is documentation-only (§1.1's table) — it never opens anything by itself | Reachability comes from the app actually listening (confirm with `kubectl exec ... -- curl localhost:<port>`) plus a Service (Day 5), not from this field |
| `kubectl rollout status` hangs indefinitely | New ReplicaSet's Pods never become Ready (bad image, failing probe) — `maxUnavailable: 0` correctly refuses to touch old, working Pods until then | `kubectl get pods -l app=<label>` to see the new ReplicaSet's Pod status directly; fix the underlying issue or `kubectl rollout undo` |
| Old Pods never terminate during a rollout | Working as designed if `maxUnavailable: 0` — old Pods only scale down as new ones become Ready, not before | Not a bug; if it never resolves, the *new* Pods are the actual problem — diagnose those |
| `kubectl set image` says `error: unable to find container named "X"` | The container name you passed doesn't match `spec.template.spec.containers[].name` in the Deployment | `kubectl get deployment <name> -o jsonpath='{.spec.template.spec.containers[*].name}'` to see the real name |
| `kubectl rollout undo` says nothing to roll back to | `revisionHistoryLimit` already pruned old ReplicaSets, or this is the first-ever revision | Check `kubectl rollout history deployment/<name>` for what's actually retained |
| Scaling up does nothing — replica count in `get deployment` doesn't match what you asked for | A `ResourceQuota` (Day 10) is blocking the extra Pods at admission time, not a scheduling failure | `kubectl describe resourcequota -n <namespace>` |

See also: [Debugging Common Kubernetes Issues](../TROUBLESHOOTING.md).

## 3. Key commands reference

| Command | Purpose |
|---|---|
| `kubectl create deployment <name> --image=<image> --dry-run=client -o yaml` | Generate a minimal Deployment manifest instead of hand-typing one — a fast way to get `deployment-minimal.yaml`'s shape for any image |
| `kubectl scale deployment <name> --replicas=N` | Manual scale |
| `kubectl rollout status deployment/<name>` | Block until rollout completes (or fails) |
| `kubectl rollout history deployment/<name> [--revision=N]` | Revision history / diff |
| `kubectl rollout undo deployment/<name> [--to-revision=N]` | Roll back |
| `kubectl rollout pause / resume deployment/<name>` | Pause a rollout mid-flight (batch multiple changes) |
| `kubectl set image deployment/<name> <container>=<image>` | Imperative image update |

Next: [Day 5 — Services & Networking](../day05-services-and-networking/README.md)
