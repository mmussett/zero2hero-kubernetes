# Day 4 — Solutions

## Exercise 1
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: scratch-test
spec:
  replicas: 2
  selector:
    matchLabels:
      app: scratch-test
  template:
    metadata:
      labels:
        app: scratch-test
    spec:
      containers:
        - name: scratch-test
          image: localhost:5000/hello-k8s:1.0.0
```
```bash
kubectl apply -f scratch-test.yaml
kubectl get pods -l app=scratch-test
kubectl delete -f scratch-test.yaml
```
If `kubectl apply` rejected this with a selector/label mismatch error, the most common cause is `spec.selector.matchLabels` and `spec.template.metadata.labels` not matching exactly — compare them key by key. If it applied but zero Pods appeared, check `kubectl describe deployment scratch-test` for a validation Event before assuming anything more exotic is wrong.

## Exercise 2
```bash
kubectl apply -f deployment-v1.yaml
kubectl get replicaset -l app=hello-k8s
RS=$(kubectl get replicaset -l app=hello-k8s -o jsonpath='{.items[0].metadata.name}')
kubectl delete deployment hello-k8s --cascade=orphan
kubectl get replicaset,pod -l app=hello-k8s   # still there
```
`--cascade=orphan` deletes the Deployment object itself but leaves its owned ReplicaSet (and that ReplicaSet's Pods) running — Kubernetes normally uses [owner references](https://kubernetes.io/docs/concepts/architecture/garbage-collection/#owners-dependents) to cascade-delete dependents automatically; `orphan` explicitly breaks that chain instead. The ReplicaSet keeps reconciling its own replica count independently — proof that the Deployment is only a *manager* of ReplicaSets, not a hard requirement for them to function.
```bash
kubectl delete replicaset $RS
```

## Exercise 3
```yaml
# deployment-v2-unavailable.yaml (diff from deployment-v2.yaml)
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 0
      maxUnavailable: 1
```
```bash
kubectl apply -f deployment-v1.yaml
kubectl apply -f deployment-v2-unavailable.yaml
kubectl get pods -l app=hello-k8s -w
```
With `maxSurge: 0, maxUnavailable: 1`, total Pod count **never exceeds** 3 (no surging above `replicas`) but **does dip to 2** at times (one unavailable while its replacement starts) — the rollout trades brief reduced capacity for never using extra resources. This is the opposite trade-off from the course default (`maxSurge:1, maxUnavailable:0`), which never drops below desired capacity but briefly uses one extra Pod's worth of resources. Choose the first on resource-constrained clusters, the second when you can't tolerate any capacity drop.

## Exercise 4
```bash
kubectl apply -f deployment-v1.yaml
kubectl apply -f deployment-v2.yaml
kubectl apply -f deployment-bad.yaml
kubectl rollout status deployment/hello-k8s --timeout=20s || true
kubectl rollout history deployment/hello-k8s
kubectl rollout undo deployment/hello-k8s --to-revision=1
kubectl rollout status deployment/hello-k8s
kubectl get deployment hello-k8s -o jsonpath='{.spec.template.spec.containers[0].image}'; echo
# -> localhost:5000/hello-k8s:1.0.0
```
`--to-revision=N` jumps directly to any retained revision, not just "one step back" — useful when a bad rollout was itself rolled forward again before anyone caught it.

## Exercise 5
```yaml
# readinessProbe.httpGet.path: /does-not-exist  in deployment-v2.yaml
```
```bash
kubectl apply -f deployment-v1.yaml
kubectl apply -f deployment-v2-badprobe.yaml
kubectl rollout status deployment/hello-k8s --timeout=30s   # times out, never completes
kubectl get pods -l app=hello-k8s
# new-RS Pods: Running, READY 0/1 (probe failing)
# old-RS Pods: still Running, READY 1/1 — none terminated
```
The rollout never completes because the Deployment controller will not scale the old ReplicaSet down until enough new Pods report **Ready** to satisfy `maxUnavailable` — with `maxUnavailable: 0` it needs the new Pods fully ready before touching the old ones at all. This is exactly the safety property that makes rolling updates safe: a bad readiness probe *blocks* the rollout indefinitely rather than taking down working capacity. `kubectl rollout undo` recovers it.
```bash
kubectl rollout undo deployment/hello-k8s
```

## Exercise 6
```yaml
spec:
  strategy:
    type: Recreate
```
```bash
kubectl apply -f deployment-v1-recreate.yaml
kubectl set image deployment/hello-k8s hello-k8s=localhost:5000/hello-k8s:1.0.0 --record=false
kubectl get pods -l app=hello-k8s -w
```
With `Recreate`, **all** old Pods are terminated first, and only once zero old Pods remain does the Deployment start creating new ones — Pod count visibly drops to 0 before climbing back to 3, meaning real downtime. You'd deliberately choose `Recreate` when the application **cannot tolerate two versions running simultaneously** — e.g. a schema-incompatible database migration bundled with the app, or a singleton process holding an exclusive lock/port that two versions can't both hold at once. RollingUpdate's brief coexistence of old+new versions is unsafe in exactly those cases.
