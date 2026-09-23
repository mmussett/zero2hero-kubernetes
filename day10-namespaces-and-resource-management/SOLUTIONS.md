---
---
# Day 10 — Solutions

## Exercise 1
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: scratch-ns
---
apiVersion: v1
kind: ResourceQuota
metadata:
  name: scratch-quota
  namespace: scratch-ns
spec:
  hard:
    pods: "3"
```
```bash
kubectl apply -f scratch-ns.yaml
for i in 1 2 3 4; do kubectl run p$i --image=busybox:1.36 -n scratch-ns -- sleep 3600; done
kubectl get pods -n scratch-ns   # only 3 ever created
kubectl delete namespace scratch-ns
```
The 4th `kubectl run` is rejected immediately with `pods "p4" is forbidden: exceeded quota` — no `LimitRange` was needed anywhere, since this quota never touches CPU or memory at all (section 1.1).

## Exercise 2
```bash
kubectl run twin --image=localhost:5000/hello-k8s:1.0.0
kubectl run twin --image=localhost:5000/hello-k8s:1.0.0 -n team-alpha
kubectl get pods -A | grep twin
```
Both succeed — namespace + name together form the real uniqueness key. A second `kubectl run twin ...` in the **same** namespace errors: `Error from server (AlreadyExists): pods "twin" already exists` — the API server enforces name uniqueness only within a namespace's scope.

## Exercise 3
```yaml
apiVersion: apps/v1
kind: Deployment
metadata: {name: many-pods, namespace: team-alpha}
spec:
  replicas: 15
  selector: {matchLabels: {app: many-pods}}
  template:
    metadata: {labels: {app: many-pods}}
    spec:
      containers:
        - name: hello-k8s
          image: localhost:5000/hello-k8s:1.0.0
          resources:
            requests: {cpu: "50m", memory: "64Mi"}
            limits: {cpu: "50m", memory: "64Mi"}
```
```bash
kubectl apply -f many-pods.yaml
kubectl get pods -n team-alpha | grep -c many-pods    # 10, not 15
kubectl describe resourcequota team-alpha-quota -n team-alpha
# pods: 10/10 — at the hard cap
```
The ReplicaSet controller keeps trying to create the remaining 5 but each creation attempt is **rejected at admission time** by the ResourceQuota (not scheduled-then-evicted — rejected before a Pod object even persists). `kubectl describe replicaset many-pods-xxxx -n team-alpha` shows repeating Events like `Error creating: pods "many-pods-xxxx" is forbidden: exceeded quota: team-alpha-quota, requested: pods=1, used: pods=10, limited: pods=10`.

## Exercise 4
```bash
kubectl apply -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata: {name: over-max, namespace: team-alpha}
spec:
  containers:
    - name: hello-k8s
      image: localhost:5000/hello-k8s:1.0.0
      resources: {limits: {memory: "1Gi"}}
EOF
```
Error: `Pod "over-max" is forbidden: maximum memory usage per Container is 512Mi, but limit is 1Gi`.
```bash
kubectl apply -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata: {name: under-min, namespace: team-alpha}
spec:
  containers:
    - name: hello-k8s
      image: localhost:5000/hello-k8s:1.0.0
      resources: {requests: {cpu: "10m"}}
EOF
```
Error: `Pod "under-min" is forbidden: minimum cpu usage per Container is 50m, but request is 10m`. Both are rejected at admission time by the `LimitRanger` admission controller (Day 17 covers admission controllers in depth) — the Pod is never created at all, not created-then-deleted.

## Exercise 5
```bash
kubectl apply -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata: {name: guaranteed-pod}
spec:
  containers:
    - name: app
      image: busybox:1.36
      command: ["sleep", "3600"]
      resources: {requests: {memory: "100Mi"}, limits: {memory: "100Mi"}}
---
apiVersion: v1
kind: Pod
metadata: {name: besteffort-pod}
spec:
  containers:
    - name: app
      image: busybox:1.36
      command: ["sleep", "3600"]
EOF
kubectl get pod guaranteed-pod -o jsonpath='{.status.qosClass}'; echo   # Guaranteed
kubectl get pod besteffort-pod -o jsonpath='{.status.qosClass}'; echo   # BestEffort
```
Under real Node memory pressure, the kubelet evicts `BestEffort` Pods **first**, then `Burstable`, and `Guaranteed` **last** (and only if it too exceeds its own limits). This ordering makes operational sense because `Guaranteed` Pods have explicitly reserved exactly the resources they use — the scheduler already accounted for them, so evicting one achieves nothing and breaks a workload that was behaving exactly as promised. `BestEffort` Pods made zero resource promises at all, so they're the safest to sacrifice first to relieve pressure, and their owners implicitly accepted that risk by not specifying requests/limits.

## Exercise 6
```bash
kubectl run persistent-pod --image=localhost:5000/hello-k8s:1.0.0
kubectl wait --for=condition=ready pod/persistent-pod --timeout=30s
NODE=$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')
kubectl taint node $NODE dedicated=gpu:NoExecute
kubectl get pod persistent-pod -w
```
With `NoExecute`, `persistent-pod` (which does not tolerate the taint) is **actively evicted/terminated**, not just blocked from future scheduling — this is the key difference from `NoSchedule`, which only prevents *new* placements and leaves already-running non-tolerating Pods untouched. `tolerationSeconds` lets a Pod tolerate a `NoExecute` taint for a **bounded grace period** before eviction (e.g. `tolerationSeconds: 300`) rather than either full immunity or immediate eviction — this is exactly the mechanism Kubernetes itself uses by default when a Node becomes `NotReady` or `Unreachable`: Pods tolerate that condition for 300 seconds (giving a flaky node a chance to recover) before being evicted and rescheduled elsewhere.
```bash
kubectl taint node $NODE dedicated=gpu:NoExecute-
kubectl delete pod persistent-pod
```

## Exercise 7
```bash
NODE=$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')
kubectl taint node $NODE workload=batch:NoSchedule
kubectl label node $NODE workload=batch

kubectl apply -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata: {name: batch-only-pod}
spec:
  tolerations:
    - {key: workload, operator: Equal, value: batch, effect: NoSchedule}
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
          - matchExpressions:
              - {key: workload, operator: In, values: ["batch"]}
  containers:
    - {name: hello-k8s, image: localhost:5000/hello-k8s:1.0.0}
EOF
kubectl run ordinary-pod --image=localhost:5000/hello-k8s:1.0.0
kubectl get pods -o wide
```
`batch-only-pod` schedules onto the tainted+labeled node (toleration lets it past the taint; affinity requires that specific node). `ordinary-pod` (no toleration) stays `Pending` if that's the only node in the cluster — the taint repels it. **Affinity alone would not be sufficient** to reserve the node: node affinity only constrains where *this particular* Pod is willing to go — it places zero restriction on *other* Pods with no affinity rule at all, which remain free to schedule onto that same node normally. Only a taint actively repels untolerating Pods; affinity is purely an attractive/opt-in force from the Pod's side, never a repellent one. Reserving a node for one workload class always requires the taint (the repellent half); affinity is only needed additionally if you also want to *pull* that workload specifically toward that node rather than merely permitting it there.
```bash
kubectl delete pod batch-only-pod ordinary-pod
kubectl taint node $NODE workload=batch:NoSchedule-
kubectl label node $NODE workload-
```
