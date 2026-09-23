# Day 3 — Pods: The Atomic Unit of Kubernetes

## Learning objectives
- Explain what a Pod is and why it can hold more than one container
- Write Pod manifests from scratch, applied declaratively
- Use liveness/readiness/startup probes correctly
- Understand init containers and the sidecar pattern
- Diagnose `Pending`, `CrashLoopBackOff`, and `ImagePullBackOff` states
- Understand the Pod lifecycle and restart policy

## 1. Concepts

**A [Pod](https://kubernetes.io/docs/concepts/workloads/pods/) is one or more containers that always land on the same Node, share a network namespace (same `localhost`, same IP), and can share storage volumes.** It's the smallest deployable unit — you never schedule a bare container in Kubernetes, only Pods.

Why group containers? The classic case is the [**sidecar pattern**](https://kubernetes.io/docs/concepts/workloads/pods/sidecar-containers/): a main application container paired with a helper (log shipper, proxy, config reloader) that needs to share the app's filesystem or network. They scale, restart, and get scheduled together as one unit.

**Pods are meant to be ephemeral and disposable.** You almost never create bare Pods in production (that's what Deployments/StatefulSets/Jobs are for, starting Day 4) — but you must understand Pods deeply because every higher-level controller is just "a thing that creates and manages Pods for you."

### 1.1 Anatomy of a minimal Pod manifest

`pod-minimal.yaml` is the smallest valid Pod that exists:

```yaml
apiVersion: v1              # Pods live in the CORE "v1" API group — no group prefix, unlike Deployments' "apps/v1"
kind: Pod
metadata:
  name: hello-world           # unlike a Deployment's Pods, THIS is the exact name you'll see in `kubectl get pods`
spec:
  containers:
    - name: hello-world         # container name — matters for -c on exec/logs once there's more than one
      image: localhost:5000/hello-k8s:1.0.0
```

Four lines of actual substance: `kind`, `metadata.name`, and one container's `name`+`image`. There's no `selector` (that's a Deployment/ReplicaSet concept — a bare Pod has nothing selecting it, it just *is*), and no `replicas` (a Pod is inherently one instance; "more instances" is exactly the problem Day 4's Deployment solves). Everything else you'll add — `ports`, `env`, `resources`, the three probe types, `restartPolicy`, `initContainers` — is additive on top of this shape, covered one at a time below.

### 1.2 Pod phases

A Pod's [**phase**](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#pod-phase) moves through `Pending → Running → Succeeded | Failed` (plus `Unknown` if the node stops reporting). A `Pending` Pod that stays Pending usually means the scheduler can't place it (insufficient resources, unsatisfiable affinity, no matching node) — always `describe` it.

### 1.3 Container states within a Pod

Each container independently reports one of three [**container states**](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#container-states): `Waiting`, `Running`, or `Terminated`. `kubectl get pods` shows `READY x/y` — y is total containers, x is how many report ready.

### 1.4 [Probes](https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/) — three different questions

| Probe | Question it answers | Effect on failure |
|---|---|---|
| `startupProbe` | "Has the app finished starting yet?" | Blocks liveness/readiness checks until it succeeds; useful for slow-starting apps so they aren't liveness-killed during startup |
| `readinessProbe` | "Can this container currently serve traffic?" | Removes the Pod from Service endpoints (Day 5) — container keeps running |
| `livenessProbe` | "Is this container still healthy?" | kubelet **kills and restarts** the container |

Getting readiness and liveness confused is one of the most common real-world outages: a liveness probe that's too aggressive restart-loops a Pod that's just temporarily slow (e.g. under load or GC pause) instead of just pulling it out of rotation.

### 1.5 [restartPolicy](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#restart-policy)

`Always` (default, used by Deployments), `OnFailure`, or `Never` (used by Jobs, Day 9). This is a Pod-level field — it dictates what the kubelet does when a container exits.

### 1.6 [Init containers](https://kubernetes.io/docs/concepts/workloads/pods/init-containers/)

**Init containers** run to completion, one at a time, in order, *before* any regular container in the Pod starts — useful for one-time setup (pulling config, waiting on a dependency, seeding a volume) that shouldn't run every time the app restarts. Unlike the sidecar pattern's containers, which run alongside the app for the Pod's whole life, an init container's job is done and it exits for good once it succeeds — `kubectl get pods` shows this as `Init:N/M` before transitioning to `PodInitializing` then `Running` (you'll see this directly in section 2.5's lab).

### Official documentation
- [Pods](https://kubernetes.io/docs/concepts/workloads/pods/)
- [Pod Lifecycle](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/)
- [Init Containers](https://kubernetes.io/docs/concepts/workloads/pods/init-containers/)
- [Sidecar Containers](https://kubernetes.io/docs/concepts/workloads/pods/sidecar-containers/)
- [Configure Liveness, Readiness and Startup Probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)
- [Assign Memory/CPU Resources to Containers](https://kubernetes.io/docs/tasks/configure-pod-container/assign-memory-resource/)
- [Pod Disruption Conditions & CrashLoopBackOff behavior](https://kubernetes.io/docs/concepts/workloads/pods/disruptions/)

## 2. Hands-on lab

```bash
cd day03-pods/manifests

# 2.1 The absolute minimum
kubectl apply -f pod-minimal.yaml
kubectl get pod hello-world
kubectl exec hello-world -- curl -s localhost:8080/
kubectl delete -f pod-minimal.yaml

# 2.2 Basic declarative Pod
kubectl apply -f pod-basic.yaml
kubectl get pod hello-pod -w      # ctrl-c once Running
kubectl get pod hello-pod -o wide
kubectl delete -f pod-basic.yaml

# 2.3 Probes
kubectl apply -f pod-probes.yaml
kubectl get pod hello-pod-probes -o jsonpath='{.status.containerStatuses[0].ready}'; echo
kubectl describe pod hello-pod-probes | grep -A5 Events
kubectl delete -f pod-probes.yaml

# 2.4 Multi-container / sidecar
kubectl apply -f pod-multicontainer.yaml
kubectl get pod sidecar-demo
kubectl exec sidecar-demo -c web -- curl -s localhost > /dev/null
kubectl logs sidecar-demo -c log-shipper --tail=5
kubectl delete -f pod-multicontainer.yaml

# 2.5 initContainers
kubectl apply -f pod-initcontainer.yaml
kubectl get pod init-demo -w      # watch Init:0/1 -> PodInitializing -> Running
kubectl logs init-demo -c fetch-config
kubectl delete -f pod-initcontainer.yaml

# 2.6 CrashLoopBackOff
kubectl apply -f pod-crashloop.yaml
kubectl get pod crash-demo -w     # watch restart count climb, backoff grow
kubectl describe pod crash-demo | tail -15
kubectl delete -f pod-crashloop.yaml
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `STATUS: Pending` and stays that way | Scheduler can't place it — see [the addendum's Pending section](../TROUBLESHOOTING.md#2-pod-stuck-pending) | `kubectl describe pod` Events name the exact reason |
| `STATUS: ImagePullBackOff` | Wrong image/tag, or registry unreachable | [Addendum §1](../TROUBLESHOOTING.md#1-pod-wont-even-start) |
| `READY 0/1`, `STATUS: Running` | `readinessProbe` failing — the container is alive but deliberately excluded from traffic | `kubectl describe pod` for the exact probe failure; verify the probe's `path`/`port` match what the app actually serves |
| `RESTARTS` climbing, `STATUS: CrashLoopBackOff` | Container exits shortly after starting | `kubectl logs <pod> --previous`; see [addendum's exit-code table](../TROUBLESHOOTING.md#crashloopbackoff) |
| Pod stuck at `Init:0/1` forever | An `initContainer` never completes (hangs, or errors and keeps retrying) | `kubectl logs <pod> -c <init-container-name>` — init container logs need the `-c` flag explicitly, `kubectl logs` alone won't show them once there's more than one container |
| `kubectl exec` into a multi-container Pod runs the wrong container | You omitted `-c <container-name>` and it defaulted to the first container in the spec | Always pass `-c` explicitly on any Pod with more than one container |

See also: [Debugging Common Kubernetes Issues](../TROUBLESHOOTING.md).

## 3. Key commands reference

| Command | Purpose |
|---|---|
| `kubectl apply -f file.yaml` | Create/update from a manifest |
| `kubectl get pod <name> -w` | Watch status changes live |
| `kubectl describe pod <name>` | Full state + Events — read the Events table bottom-up |
| `kubectl logs <pod> -c <container> [--previous]` | Logs (`--previous` = logs from before the last restart) |
| `kubectl exec -it <pod> [-c container] -- sh` | Shell into a specific container |
| `kubectl delete -f file.yaml` | Delete what the file defines |

Next: [Day 4 — ReplicaSets, Deployments & Rollouts](../day04-deployments-replicasets/README.md)
