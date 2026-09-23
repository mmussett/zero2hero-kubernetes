# Day 8 — Solutions

## Exercise 1
```yaml
apiVersion: v1
kind: Service
metadata:
  name: scratch-sts
spec:
  clusterIP: None
  selector:
    app: scratch-sts
  ports:
    - port: 8080
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: scratch-sts
spec:
  serviceName: scratch-sts
  replicas: 2
  selector:
    matchLabels:
      app: scratch-sts
  template:
    metadata:
      labels:
        app: scratch-sts
    spec:
      containers:
        - name: scratch-sts
          image: localhost:5000/hello-k8s:1.0.0
```
```bash
kubectl apply -f scratch-sts.yaml
kubectl get pods -l app=scratch-sts   # scratch-sts-0, scratch-sts-1
kubectl delete -f scratch-sts.yaml
```
The two required differences from a plain Deployment are exactly `serviceName` and `kind: StatefulSet` itself — everything else in `spec` is the identical shape you already know.

## Exercise 2
```yaml
apiVersion: apps/v1
kind: Deployment
metadata: {name: hello-deploy-compare}
spec:
  replicas: 3
  selector: {matchLabels: {app: hello-deploy-compare}}
  template:
    metadata: {labels: {app: hello-deploy-compare}}
    spec:
      initContainers:
        - name: record-identity
          image: busybox:1.36
          command: ["sh", "-c", 'echo "I am $(hostname)" > /data/identity.txt']
          volumeMounts: [{name: data, mountPath: /data}]
      containers:
        - name: hello-k8s
          image: localhost:5000/hello-k8s:1.0.0
          volumeMounts: [{name: data, mountPath: /data}]
      volumes:
        - name: data
          emptyDir: {}
```
```bash
kubectl apply -f hello-deploy-compare.yaml
kubectl get pods -l app=hello-deploy-compare
# hello-deploy-compare-7d9f8c6b9d-a1b2c, -x9k2m, -p7q3r  <- random suffixes
kubectl get pods -l app=hello-stateful
# hello-stateful-0, hello-stateful-1, hello-stateful-2   <- stable, numbered
```
Deleting a Pod from the Deployment produces a **replacement with a brand-new random name** and a brand-new `emptyDir` (empty again — `identity.txt` is gone, since `emptyDir` isn't even a PVC). Deleting a Pod from the StatefulSet produces a replacement with the **exact same name** and **exact same PVC**, so `identity.txt` content is preserved. This is the entire value proposition of StatefulSets made concrete.

## Exercise 3
The reasoning: PVCs (and the data they represent) are treated as far too precious to delete automatically just because a StatefulSet was scaled down or deleted — an accidental `kubectl scale --replicas=0` or a typo'd `kubectl delete statefulset` must never silently destroy a production database's data. Requiring an explicit, separate `kubectl delete pvc` is a deliberate safety guard, consistent with the Day 7 lesson that reclaim/deletion of storage should always be a conscious, separate action from deleting the workload that used it.

To opt into automatic deletion (available since Kubernetes 1.27+ stable):
```yaml
spec:
  persistentVolumeClaimRetentionPolicy:
    whenDeleted: Delete   # delete PVCs when the StatefulSet itself is deleted
    whenScaled: Delete    # delete PVCs for replicas removed by scaling down
```
(Default for both is `Retain`, matching the behavior you observed.)

## Exercise 4
```bash
kubectl delete -f statefulset.yaml -f headless-service.yaml --ignore-not-found
kubectl delete pvc -l app=hello-stateful
# edit statefulset.yaml: add "sleep 15 && " before the echo in record-identity's command
kubectl apply -f headless-service.yaml
time (kubectl apply -f statefulset.yaml && kubectl wait --for=condition=ready pod -l app=hello-stateful --timeout=90s)
```
Total time is roughly 3× ~15s (≈45s+), because `podManagementPolicy: OrderedReady` (the default) forces `-1`'s creation to wait until `-0` is fully `Running and Ready`, and `-2` to wait for `-1` — each replica's ~15s init delay is serialized, not overlapped. Setting `podManagementPolicy: Parallel` in `spec` removes this ordering constraint entirely, launching all replicas' init containers simultaneously, cutting total time to roughly one replica's startup time — appropriate when replicas have no startup dependency on each other (unlike, say, a database primary that followers need already running).

## Exercise 5
```bash
sed 's/serviceName: hello-stateful/serviceName: does-not-exist/' statefulset.yaml \
  | sed 's/name: hello-stateful/name: broken-sts/' > broken-sts.yaml
kubectl apply -f broken-sts.yaml
kubectl get pods -l app=hello-stateful
```
Pods **do** start and reach `Running`/`Ready` normally — the StatefulSet controller does not validate that the named Service actually exists before creating Pods. What breaks is purely DNS: `nslookup broken-sts-0.does-not-exist.default.svc.cluster.local` fails (`NXDOMAIN`/server can't find it), because there's no headless Service for CoreDNS to generate per-Pod records from. This is a common real-world misconfiguration — Pods look perfectly healthy in `kubectl get pods`, but nothing can address them individually, so always verify the headless Service exists and its `clusterIP` is genuinely `None` when debugging "StatefulSet Pods are up but peers can't find each other."
```bash
kubectl delete -f broken-sts.yaml
kubectl delete pvc -l app=hello-stateful
```

## Exercise 6
```bash
kubectl delete pod hello-stateful-0
kubectl get pods -l app=hello-stateful -w
```
Only `hello-stateful-0` is touched — a fresh `hello-stateful-0` is created (reusing its PVC), while `-1` and `-2` are completely undisturbed throughout (no restarts, no re-creation). This is actually **identical** blast-radius behavior to a Deployment losing one Pod — the controller only replaces the specific Pod that's gone, not the whole set — the real difference Day 8 teaches isn't about failure blast radius, it's that the *replacement* for `-0` keeps `-0`'s exact name and storage, where a Deployment's replacement would get a random name and (with `emptyDir`) fresh empty storage.
