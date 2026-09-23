---
---
# Day 10 — Namespaces, Resource Management & Scheduling Controls

## Learning objectives
- Use Namespaces to logically partition a cluster and understand what they do *not* isolate
- Enforce per-namespace resource ceilings with ResourceQuota
- Set sane per-container defaults with LimitRange
- Understand the full relationship between requests, limits, and QoS classes
- Control *where* Pods are scheduled using taints/tolerations and node affinity

## 1. Concepts

### 1.1 Anatomy of a minimal Namespace and ResourceQuota

A [**Namespace**](https://kubernetes.io/docs/concepts/overview/working-with-objects/namespaces/) needs nothing but a name:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: hello-world
```

That's genuinely the entire object — no `spec` at all. A [**ResourceQuota**](https://kubernetes.io/docs/concepts/policy/resource-quotas/) is almost as small; you list only the specific things you want to cap:

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: hello-world-quota
  namespace: hello-world   # ResourceQuota is namespaced — it always targets ONE namespace
spec:
  hard:
    pods: "5"                # cap object COUNT — no CPU/memory limits required at all
```

`hard` accepts any subset of the quota-able resources (§1.3's fuller example caps CPU, memory, and PVC count too) — capping just `pods` alone, as here, is a completely valid, minimal quota that needs no `LimitRange` companion, since it never touches CPU/memory at all.

### 1.2 Namespaces — scoping, not sandboxing

A [**Namespace**](https://kubernetes.io/docs/concepts/overview/working-with-objects/namespaces/) partitions object *names* and, combined with today's other tools, resource consumption and (Day 16) permissions. Object names only need to be unique **within** a namespace — you can have a `hello-k8s` Deployment in both `team-alpha` and `team-beta` simultaneously.

**What namespaces are NOT, by default:**
- **Not a network boundary** — a Pod in `team-alpha` can reach a Pod in `team-beta` over the network unless a NetworkPolicy (Day 14) says otherwise.
- **Not a resource boundary** — without a ResourceQuota, a namespace can consume unlimited cluster resources.
- **Not a security boundary** — without RBAC (Day 16), any user with cluster access can act across every namespace.

Some cluster-scoped objects (Nodes, PersistentVolumes, ClusterRoles, Namespaces themselves) don't live in any namespace at all — `kubectl api-resources --namespaced=false` lists them.

### 1.3 ResourceQuota — a namespace-wide budget

A [**ResourceQuota**](https://kubernetes.io/docs/concepts/policy/resource-quotas/) caps the *total* resource consumption (and, optionally, object counts) across an entire namespace. Critically: **once a ResourceQuota exists in a namespace covering CPU or memory, every Pod created there must explicitly specify `requests`/`limits` for those resources, or the Pod is rejected outright** — this interacts directly with LimitRange (below), which is usually deployed alongside a ResourceQuota specifically to avoid that friction.

### 1.4 LimitRange — sane per-container defaults and bounds

A [**LimitRange**](https://kubernetes.io/docs/concepts/policy/limit-range/) operates on individual Pods/Containers (not the namespace total) and does two things:
1. **Defaults** — auto-injects `requests`/`limits` into any container that doesn't specify them (this is what satisfies the ResourceQuota requirement above without every developer having to know the exact numbers).
2. **Bounds** — rejects any container whose explicit `requests`/`limits` fall outside a configured `min`/`max`.

### 1.5 Requests vs. limits — full picture, and QoS classes

Recall Day 3: `requests` is what the **scheduler** uses to decide if a Pod fits on a Node (a Node needs that much *unreserved* allocatable capacity); `limits` is a hard ceiling the kernel cgroup enforces at runtime (CPU is throttled; memory over-limit gets the container OOMKilled, Day 1 Exercise 4). The relationship between a Pod's requests and limits across all its containers determines its [**Quality of Service (QoS) class**](https://kubernetes.io/docs/concepts/workloads/pods/pod-qos/), used by the kubelet to decide **eviction order** under Node memory pressure:

| QoS class | Condition | Evicted... |
|---|---|---|
| `Guaranteed` | Every container sets `requests == limits` for both CPU and memory | Last |
| `Burstable` | At least one container sets a request, but not `Guaranteed`'s exact-match condition | Middle |
| `BestEffort` | No container sets any request or limit at all | First |

This is a direct, practical consequence of numbers you type into YAML — a production database Pod should almost always be `Guaranteed`; a low-priority batch job can safely be `BestEffort`.

### 1.6 Scheduling controls: taints, tolerations & node affinity

Two independent mechanisms control *where* the scheduler is allowed to place a Pod:

- **Taints** (applied to a Node) + **tolerations** (applied to a Pod) — a taint **repels** Pods from a Node unless the Pod explicitly tolerates it. This is an "opt-in via exception" model: by default nothing can schedule onto a tainted Node. `effect: NoSchedule` blocks new placements; `NoExecute` additionally evicts already-running Pods that don't tolerate it. (You already saw this in Day 9's DaemonSet, which tolerated the built-in `node-role.kubernetes.io/control-plane` taint to run everywhere.)
- **Node affinity** (applied to a Pod) — the inverse direction: a Pod expresses a **preference or requirement** for Node labels, without the Node needing any taint at all. `requiredDuringSchedulingIgnoredDuringExecution` is a hard requirement (Pod stays `Pending` if unmet); `preferredDuringSchedulingIgnoredDuringExecution` is a soft preference the scheduler tries to honor but won't block on.

Rule of thumb: use **taints/tolerations** to *keep general workloads off* specialized Nodes (reserve GPU nodes for GPU workloads); use **node affinity** to *pull specific workloads toward* Nodes with a needed characteristic (an SSD, a specific zone). Production clusters frequently combine both on the same specialized node pool.

### Official documentation
- [Namespaces](https://kubernetes.io/docs/concepts/overview/working-with-objects/namespaces/)
- [Resource Quotas](https://kubernetes.io/docs/concepts/policy/resource-quotas/)
- [Limit Ranges](https://kubernetes.io/docs/concepts/policy/limit-range/)
- [Pod Quality of Service Classes](https://kubernetes.io/docs/concepts/workloads/pods/pod-qos/)
- [Managing Resources for Containers](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)
- [Taints and Tolerations](https://kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/)
- [Assigning Pods to Nodes (nodeSelector / affinity)](https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/)

## 2. Hands-on lab

```bash
cd day10-namespaces-and-resource-management/manifests

# 2.1 The absolute minimum
kubectl apply -f namespace-minimal.yaml
kubectl apply -f resourcequota-minimal.yaml
kubectl describe resourcequota hello-world-quota -n hello-world
kubectl delete -f resourcequota-minimal.yaml -f namespace-minimal.yaml

# 2.2 Namespaces and cluster-scoped vs. namespaced resources
kubectl apply -f namespace.yaml
kubectl api-resources --namespaced=true | head -10
kubectl api-resources --namespaced=false | head -10

# 2.3 Apply quota and limit range
kubectl apply -f resourcequota.yaml
kubectl apply -f limitrange.yaml
kubectl describe resourcequota team-alpha-quota -n team-alpha
kubectl describe limitrange team-alpha-limits -n team-alpha

# 2.4 LimitRange auto-defaulting
kubectl apply -f pod-no-resources.yaml
kubectl get pod no-resources-pod -n team-alpha -o jsonpath='{.spec.containers[0].resources}'; echo
# requests/limits were injected even though the manifest specified none

# 2.5 QoS class
kubectl get pod no-resources-pod -n team-alpha -o jsonpath='{.status.qosClass}'; echo   # Burstable

# 2.6 ResourceQuota rejecting an over-budget deployment
kubectl apply -f deployment-oversized.yaml
kubectl get events -n team-alpha --sort-by=.lastTimestamp | tail -5
kubectl get replicaset -n team-alpha   # fewer Pods than requested — quota blocked some
kubectl describe resourcequota team-alpha-quota -n team-alpha   # Used vs Hard

# 2.7 Taints and tolerations
NODE=$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')
kubectl taint node $NODE dedicated=gpu:NoSchedule
kubectl run untolerating --image=localhost:5000/hello-k8s:1.0.0
kubectl get pod untolerating -w    # stays Pending
kubectl describe pod untolerating | grep -A3 Events   # "untolerated taint"
kubectl apply -f pod-toleration.yaml
kubectl get pod tolerating-pod -w  # schedules fine — it tolerates the taint
kubectl taint node $NODE dedicated=gpu:NoSchedule-   # remove the taint (trailing "-")

# 2.8 Node affinity
kubectl label node $NODE disktype=ssd
kubectl apply -f pod-node-affinity.yaml
kubectl get pod affinity-pod -o wide   # scheduled — label matched
kubectl label node $NODE disktype-

# 2.9 Clean up
kubectl delete pod untolerating tolerating-pod affinity-pod --ignore-not-found
kubectl delete namespace team-alpha
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Deployment's replica count in `kubectl get deployment` never reaches what you asked for, no scheduling errors anywhere | A `ResourceQuota` in that namespace is rejecting the extra Pods at **admission time** — they never even get created, so there's nothing for the scheduler to reject | `kubectl describe resourcequota -n <namespace>`; compare `Used` against `Hard` |
| New Pod rejected outright with `exceeded quota` in the error | Same as above, but on a single `kubectl run`/`apply` instead of a Deployment scale-out | Lower the request, or raise the quota if you have permission to |
| Pod rejected with `maximum ... usage per Container is X, but limit is Y` | A `LimitRange` caps container resources tighter than what you asked for | `kubectl describe limitrange -n <namespace>` for the exact `min`/`max` bounds |
| Pod got resource `requests`/`limits` you never specified | A `LimitRange`'s `defaultRequest`/`default` auto-injected them — this is a feature, not a bug (section 1.3) | `kubectl get pod <name> -o jsonpath='{.spec.containers[0].resources}'` to see what actually landed |
| Pod stuck `Pending`, Events mention an untolerated taint | A taint exists on every candidate Node and this Pod has no matching `toleration` | `kubectl describe node <node>` to see its taints; add a matching toleration or remove the taint |
| Pod scheduled somewhere you didn't expect, ignoring `nodeAffinity` | You used `preferredDuringSchedulingIgnoredDuringExecution` (a soft preference) when you meant `requiredDuringSchedulingIgnoredDuringExecution` (a hard requirement) | Check which one is actually in the manifest — "preferred" can and will be overridden if no matching Node has room |

See also: [Debugging Common Kubernetes Issues](../TROUBLESHOOTING.md).

## 3. Key commands reference

| Command | Purpose |
|---|---|
| `kubectl create namespace <name>` | Imperative namespace creation |
| `kubectl config set-context --current --namespace=<ns>` | Change your shell's default namespace (avoid typing `-n` constantly) |
| `kubectl describe resourcequota <name> -n <ns>` | See Used vs. Hard limits |
| `kubectl get pod <name> -o jsonpath='{.status.qosClass}'` | Check a Pod's QoS class |
| `kubectl taint node <node> key=value:Effect` | Add a taint (append `-` to remove) |
| `kubectl label node <node> key=value` | Add a label (append `-` to remove) |

Next: [Day 11 — Ingress](../day11-ingress/README.md)
