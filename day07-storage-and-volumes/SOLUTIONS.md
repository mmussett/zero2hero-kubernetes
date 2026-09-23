# Day 7 — Solutions

## Exercise 1
```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: scratch-pvc
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: local-path
  resources:
    requests:
      storage: 500Mi
```
```bash
kubectl apply -f scratch-pvc.yaml
kubectl get pvc scratch-pvc -w   # ctrl-c once Bound
kubectl get pv                    # a PV was created automatically to satisfy it
kubectl delete -f scratch-pvc.yaml
```
The `local-path` StorageClass's provisioner created a matching PV entirely on its own the moment the claim appeared — this is dynamic provisioning (section 1.3), and it's why nothing you wrote ever mentions a disk path.

## Exercise 2
```yaml
apiVersion: v1
kind: Pod
metadata: {name: emptydir-demo}
spec:
  containers:
    - name: writer
      image: busybox:1.36
      command: ["sh", "-c", "date >> /data/log.txt; sleep 3600"]
      volumeMounts: [{name: scratch, mountPath: /data}]
    - name: reader
      image: busybox:1.36
      command: ["sh", "-c", "sleep 3600"]
      volumeMounts: [{name: scratch, mountPath: /readonly-data}]
  volumes:
    - name: scratch
      emptyDir: {}
```
```bash
kubectl apply -f emptydir-2container.yaml
kubectl exec emptydir-demo -c reader -- cat /readonly-data/log.txt   # same content writer produced
```
This proves an `emptyDir` volume is a single shared storage location for the whole **Pod** — every container that mounts it (regardless of the mount path each one chooses) sees the same underlying data, updated live as any container writes to it. This is the mechanism the Day 3 sidecar pattern relies on.

## Exercise 3
```bash
kubectl get pv -l ... -o jsonpath='{.items[0].spec.persistentVolumeReclaimPolicy}'
# Delete
kubectl apply -f pvc-local-path.yaml -f pod-with-pvc.yaml
kubectl exec pvc-demo -- cat /data/persistent-log.txt
kubectl delete pod pvc-demo
kubectl delete pvc hello-pvc
kubectl get pv    # the PV that backed hello-pvc is GONE
```
The default reclaim policy for dynamically-provisioned PVs (including k3s's `local-path` class) is `Delete` — deleting the PVC immediately deletes the backing PV **and its data**, with no confirmation and no recovery. This is a real production risk: a mistaken `kubectl delete pvc` on a database's claim permanently destroys its data unless you've explicitly set `persistentVolumeReclaimPolicy: Retain` (either on a static PV, or via a custom StorageClass with `reclaimPolicy: Retain`) or you have external backups.

## Exercise 4
```bash
kubectl apply -f - <<'EOF'
apiVersion: v1
kind: PersistentVolumeClaim
metadata: {name: too-big-pvc}
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: manual
  resources: {requests: {storage: 10Gi}}
EOF
kubectl get pvc too-big-pvc
# STATUS: Pending
kubectl describe pvc too-big-pvc
```
It stays `Pending` indefinitely. Because `manual` is a static (non-dynamically-provisioning) StorageClass here, Kubernetes can only bind the PVC to an **existing** PV matching the class and with capacity **>=** the request — no PV of that class offers 10Gi (only the 500Mi one exists), so there's nothing to bind to, and nothing will provision a new one automatically. `describe` shows an Event like `no persistent volumes available for this claim and no storage class is set` or, since a class *is* set but nothing provisions it dynamically, it simply waits forever. Contrast with `local-path` (Exercise verifies dynamic provisioning always succeeds regardless of requested size, since it just creates a directory).
```bash
kubectl delete pvc too-big-pvc
```

## Exercise 5
```yaml
apiVersion: apps/v1
kind: Deployment
metadata: {name: rwo-test}
spec:
  replicas: 2
  selector: {matchLabels: {app: rwo-test}}
  template:
    metadata: {labels: {app: rwo-test}}
    spec:
      containers:
        - name: app
          image: busybox:1.36
          command: ["sleep", "3600"]
          volumeMounts: [{name: data, mountPath: /data}]
      volumes:
        - name: data
          persistentVolumeClaim: {claimName: hello-pvc}
```
```bash
kubectl apply -f pvc-local-path.yaml
kubectl apply -f rwo-deployment.yaml
kubectl get pods -l app=rwo-test
```
On this single-node lab cluster, **both** replicas typically reach `Running` and can both mount the PVC, because `ReadWriteOnce` restricts a volume to being mounted by Pods on **one Node at a time** — and since there's only one Node, both Pods are on it, satisfying the constraint. On a real multi-node cluster, if the scheduler tried to place the second replica on a *different* Node, that Pod would sit `Pending`/`ContainerCreating` with a `FailedAttachVolume`/multi-attach error in its Events, because RWO explicitly forbids simultaneous multi-node attachment — this is precisely why databases needing true multi-node write access require either `ReadWriteMany` storage or an architecture (like StatefulSets with one PVC per replica, Day 8) that avoids sharing one volume across replicas at all.
```bash
kubectl delete -f rwo-deployment.yaml -f pvc-local-path.yaml
```

## Exercise 6
```bash
kubectl apply -f pvc-local-path.yaml -f pod-with-pvc.yaml
PV=$(kubectl get pvc hello-pvc -o jsonpath='{.spec.volumeName}')
kubectl delete pv $PV
kubectl get pv $PV
# still there, but Terminating / stuck
kubectl describe pv $PV | grep -A2 Finalizers
```
The `kubectl delete pv` command returns immediately but the PV enters (and stays in) `Terminating` state — it is not actually removed. `describe pv` shows a `Finalizers: [kubernetes.io/pv-protection]` entry. A **finalizer** is a marker telling the API server "don't fully remove this object until whatever added this finalizer removes it" — `pv-protection` specifically blocks deletion while the PV is still `Bound` to a PVC, to stop an admin from accidentally deleting storage a live claim (and possibly a live Pod) still depends on. Once you delete the Pod and the PVC, the finalizer is removed automatically and the PV deletion (which was queued) completes.
```bash
kubectl delete pod pvc-demo
kubectl delete pvc hello-pvc
kubectl get pv   # now actually gone
```

## Exercise 7
```bash
kubectl apply -f pvc-local-path.yaml -f pod-with-pvc.yaml
PV=$(kubectl get pvc hello-pvc -o jsonpath='{.spec.volumeName}')
kubectl get pv $PV -o yaml | grep -A3 hostPath
# path: /var/lib/rancher/k3s/storage/<pvc-uid>_default_hello-pvc
sudo cat /var/lib/rancher/k3s/storage/<pvc-uid>_default_hello-pvc/persistent-log.txt
```
The file content matches exactly what `kubectl exec pvc-demo -- cat /data/persistent-log.txt` showed. This proves k3s's `local-path-provisioner` "dynamic provisioning" is, under the hood, exactly the same mechanism as the `hostPath` demo in section 2.2 — it just automates creating a uniquely-named host directory and wiring up the PV/PVC objects for you. That's precisely why `local-path` shares `hostPath`'s core limitation (node-tied, no real high availability) despite feeling like "real" dynamic storage from the PVC's perspective — a cloud provider's StorageClass (e.g. AWS EBS/GCP PD) instead provisions genuine network-attached block storage that can follow a Pod to any Node in the cluster, which is the production-grade equivalent of what you just did by hand.
```bash
kubectl delete -f pod-with-pvc.yaml -f pvc-local-path.yaml
```
