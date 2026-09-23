# Day 21 — Autoscaling & Advanced Rollout Strategies

## Learning objectives
- Configure and observe the Horizontal Pod Autoscaler (HPA) scaling on live CPU metrics
- Understand HPA's scale-up/scale-down decision loop and stabilization windows
- Understand what Vertical Pod Autoscaler and Cluster Autoscaler solve, conceptually
- Implement blue-green deployment using a Service selector swap
- Implement a basic canary release using replica-ratio traffic splitting
- Choose the right rollout strategy for a given risk profile

## 1. Concepts

### 1.1 Anatomy of a minimal HorizontalPodAutoscaler

`hpa-minimal.yaml` is the smallest useful HPA — no scale-down tuning, one metric:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: hello-world-hpa
spec:
  scaleTargetRef:               # WHICH object to scale — must already exist
    apiVersion: apps/v1
    kind: Deployment
    name: php-apache
  minReplicas: 1
  maxReplicas: 5
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 50   # target: 50% of the Deployment's requests.cpu (§1.2)
```

`scaleTargetRef` is the one field that makes an HPA meaningless without something else already deployed — unlike every other manifest this course has started with, an HPA has no content of its own to run; it purely edits another object's `replicas` field. `behavior.scaleDown.stabilizationWindowSeconds` (used later this day) is a tuning knob layered on top, not part of the minimum.

### 1.2 Horizontal Pod Autoscaler (HPA) — scale the number of replicas

Recall Day 18: metrics-server exposes live CPU/memory usage via the Metrics API. The [**HorizontalPodAutoscaler**](https://kubernetes.io/docs/concepts/workloads/autoscaling/) reads that API on a control loop (every 15s by default) and adjusts a target's `replicas` field to drive observed metrics toward a target value — it does this by directly editing the target Deployment's `spec.replicas`, the exact same field `kubectl scale` (Day 4) edits by hand; the HPA is simply an automated controller doing that for you continuously.

**The core formula** (simplified from the [official algorithm](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/#algorithm-details)):
```
desiredReplicas = ceil(currentReplicas × (currentMetricValue / desiredMetricValue))
```
With `averageUtilization: 50` (i.e., 50% of the CPU **request**, not limit — this is why every Pod under HPA control must set `resources.requests.cpu`, or the HPA has nothing to compute a percentage against and simply won't function) and current average usage at 200%, the HPA roughly quadruples replica count, capped by `maxReplicas`.

**Scale-down is deliberately more cautious than scale-up** — real traffic is often bursty, and immediately scaling down the moment load drops risks flapping (scale down, traffic spikes again seconds later, scale up again, repeat). The `behavior.scaleDown.stabilizationWindowSeconds` field (60s in today's HPA — production often uses 300s+) requires load to stay low for that entire window before any scale-down happens, while scale-up by default reacts almost immediately.

### 1.3 Vertical Pod Autoscaler (VPA) — scale the size of each replica

Where HPA changes **how many** replicas exist, [**VPA**](https://github.com/kubernetes/autoscaler/tree/master/vertical-pod-autoscaler) changes **how big** each replica's `requests`/`limits` are, based on observed historical usage — directly addressing the Day 10 problem of guessing the "right" request/limit numbers by hand. VPA has three modes: `Off` (recommendation only — shows you what it *would* set, without acting), `Initial` (sets requests only at Pod creation), and `Auto` (actively resizes — which historically required **evicting and recreating** the Pod to change its resources, since resizing a running container's cgroup limits in place wasn't supported until Kubernetes's newer [in-place Pod resize](https://kubernetes.io/docs/tasks/configure-pod-container/resize-container-resources/) feature). **VPA and HPA should generally not both control CPU/memory for the same workload simultaneously** — they can fight each other's decisions.

> **Why VPA isn't hands-on today:** VPA is not a built-in Kubernetes API (like HPA is) — it's a separate open-source project you install yourself (multiple controller components, its own CRDs, and typically a metrics-history-aware recommender). Installing and demonstrating it reliably needs more resources and setup time than this single-node lab budget allows; today covers it conceptually so you recognize it and know when to reach for it, with links to install it yourself later.

### 1.4 Cluster Autoscaler — scale the number of Nodes

[**Cluster Autoscaler**](https://kubernetes.io/docs/concepts/cluster-administration/cluster-autoscaling/) operates one level up from both of the above: when Pods are `Pending` because no existing Node has room (HPA scaling out just created 5 new replicas, but the cluster is full), Cluster Autoscaler provisions **new Nodes** via your infrastructure provider's API; when Nodes sit mostly idle, it deprovisions them to save cost. This fundamentally requires integration with a real cloud provider's VM/instance-group API (AWS Auto Scaling Groups, GCP Managed Instance Groups, etc.) — **there is no meaningful way to demonstrate it on a single-node local k3s lab**, since there's no infrastructure API underneath to provision from. Know the concept and where it fits (it's the layer *above* HPA/VPA in the full autoscaling picture below) — you'll configure it for real the day you operate a cloud-hosted cluster.

```
 Cluster Autoscaler  ─── adds/removes NODES ───▶  more/less total cluster capacity
        ▲ triggered by Pending Pods
        │
 Horizontal Pod Autoscaler ─── adds/removes PODS (replicas) ───▶  more/less instances of one workload
        ▲ triggered by per-Pod metric vs. target
        │
 Vertical Pod Autoscaler ─── resizes EACH POD's requests/limits ───▶  right-sized individual instances
```

### 1.5 Rollout strategies beyond RollingUpdate

Day 4 covered `RollingUpdate` and `Recreate` — Kubernetes's two **native** Deployment strategies. Two more patterns are achieved by **combining Kubernetes primitives you already know**, not a dedicated built-in field:

- **Blue-green**: run two complete, independent Deployments (`blue` = current, `green` = new) simultaneously at full scale, verify `green` directly (e.g. via `kubectl port-forward` to a `green`-only Pod, bypassing the shared Service), then cut over **all** traffic in one atomic step by changing a Service's `selector` — instant, and instantly reversible by flipping the selector back, at the cost of running 2× the resources during the transition.
- **Canary**: route a **small percentage** of production traffic to the new version while most traffic still hits the old version, observe real metrics/errors from that small slice, then gradually shift more traffic over (or abort and roll back) based on what you observe. Today's lab approximates canary weighting via **replica ratio** behind one Service (simple, works anywhere) — production setups more often use an Ingress controller or service mesh's native weighted-traffic-splitting (e.g. Traefik `TraefikService` weights, Istio `VirtualService` weights) for precise percentages independent of replica count.

| Strategy | Rollback speed | Extra resource cost during rollout | Blast radius of a bad release |
|---|---|---|---|
| `RollingUpdate` (Day 4) | Fast (`rollout undo`) | Small (`maxSurge`) | Gradual — some fraction of traffic hits bad Pods as they roll in |
| `Recreate` (Day 4) | Requires a full redeploy | None | 100% (real downtime either way) |
| Blue-green | Instant (flip selector back) | 2× replicas, temporarily | Zero, until cutover — then 100% until flipped back |
| Canary | Fast (scale canary to 0) | Small (a few extra replicas) | Small, by design — that's the entire point |

### Official documentation
- [Horizontal Pod Autoscaling](https://kubernetes.io/docs/concepts/workloads/autoscaling/)
- [HorizontalPodAutoscaler Walkthrough](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale-walkthrough/)
- [HPA Algorithm Details](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/#algorithm-details)
- [Vertical Pod Autoscaler (project)](https://github.com/kubernetes/autoscaler/tree/master/vertical-pod-autoscaler)
- [In-place Update of Pod Resources](https://kubernetes.io/docs/tasks/configure-pod-container/resize-container-resources/)
- [Cluster Autoscaler (project)](https://kubernetes.io/docs/concepts/cluster-administration/cluster-autoscaling/)
- [Deployment strategies](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#strategy)

## 2. Hands-on lab

```bash
cd day21-autoscaling-and-rollouts/manifests

# 2.1 The absolute minimum
kubectl apply -f hpa-app.yaml
kubectl wait --for=condition=ready pod -l run=php-apache --timeout=60s
kubectl apply -f hpa-minimal.yaml
kubectl get hpa hello-world-hpa   # TARGETS shows a real percentage once metrics-server reports usage
kubectl delete -f hpa-minimal.yaml

# 2.2 Deploy the full autoscaler with scale-down tuning
kubectl apply -f hpa.yaml
kubectl get hpa php-apache -w &     # leave this running in the background to watch live
sleep 2

# 2.3 Baseline — no load, should sit at minReplicas
kubectl top pod -l run=php-apache

# 2.4 Generate load and watch it scale out
kubectl apply -f load-generator.yaml
sleep 90   # give the HPA a few reconcile cycles to react
kubectl get hpa php-apache
kubectl get pods -l run=php-apache
kubectl describe hpa php-apache | tail -15   # Events show each scaling decision and why

# 2.5 Remove load and watch the stabilization window before scale-down
kubectl delete pod load-generator
sleep 90
kubectl get hpa php-apache
kubectl get pods -l run=php-apache   # back down toward minReplicas after the 60s stabilization window
kill %1 2>/dev/null   # stop the background watch from 2.1

# 2.6 Blue-green deployment
kubectl apply -f bluegreen-blue.yaml -f bluegreen-green.yaml -f bluegreen-service.yaml
kubectl wait --for=condition=ready pod -l track=blue --timeout=60s
kubectl wait --for=condition=ready pod -l track=green --timeout=60s
kubectl port-forward svc/hello-bg-svc 8080:80 &
curl localhost:8080/   # "I am BLUE"
kubectl patch service hello-bg-svc -p '{"spec":{"selector":{"track":"green"}}}'
curl localhost:8080/   # "I am GREEN" — instant cutover, zero rolling delay
kill %1

# 2.7 Canary deployment (replica-ratio weighted)
kubectl apply -f canary-stable.yaml -f canary-canary.yaml
kubectl wait --for=condition=ready pod -l track=stable --timeout=60s
kubectl wait --for=condition=ready pod -l track=canary --timeout=60s
kubectl port-forward svc/hello-canary-svc 8081:80 &
for i in $(seq 1 20); do curl -s localhost:8081/ | grep -o '"message":"[^"]*"'; done | sort | uniq -c
# roughly 18 STABLE : 2 CANARY, matching the 9:1 replica ratio
kill %1

# 2.8 Clean up
kubectl delete -f .
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `kubectl get hpa` shows `<unknown>` under `TARGETS` | metrics-server isn't reporting data yet, or the target Pods have **no `resources.requests` set at all** — HPA computes utilization as a percentage of requests, and can't without them | `kubectl top pod` to confirm metrics-server itself works; add `resources.requests.cpu` to the target Deployment if missing |
| HPA never scales up despite obviously high load | `maxReplicas` already reached (check `describe hpa` for `ScalingLimited: True`), or the metric it's watching isn't the one actually under pressure | `kubectl describe hpa` Events explain exactly what's blocking further scaling |
| HPA scales down immediately after load drops, then back up seconds later (flapping) | `stabilizationWindowSeconds` on scale-down is too short or unset for a bursty workload | Increase it (this course's example uses 60s; production often uses 300s+) |
| Blue-green cutover (`kubectl patch service`) doesn't seem to change anything | Cached DNS/connection reuse on the client side, or you patched the wrong Service | `curl` fresh (not from a client holding an old connection open) and confirm which Service you actually patched with `kubectl get svc -o yaml` |
| Canary traffic ratio doesn't match the replica ratio you set | Small sample size — see Day 21's own note on this; load-balancing is probabilistic per-request, not a strict round-robin guarantee | Test with a larger number of requests before concluding the ratio is wrong |

See also: [Debugging Common Kubernetes Issues](../TROUBLESHOOTING.md).

## 3. Key commands reference

| Command | Purpose |
|---|---|
| `kubectl get hpa [-w]` | Watch current/target metric value and replica count |
| `kubectl describe hpa <name>` | See scaling decision Events with reasoning |
| `kubectl autoscale deployment <name> --cpu-percent=50 --min=1 --max=6` | Imperatively create an HPA |
| `kubectl patch service <name> -p '{"spec":{"selector":{...}}}'` | Instant traffic cutover for blue-green |
| `kubectl scale deployment <canary-deploy> --replicas=N` | Adjust canary traffic weight by replica ratio |

Next: [Day 22 — Custom Resources, Operators & Kustomize](../day22-crds-operators-and-kustomize/README.md)
