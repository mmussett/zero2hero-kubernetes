---
---
# Day 7 — Storage: Volumes, PersistentVolumes, PersistentVolumeClaims & StorageClasses

## Learning objectives
- Explain why container filesystems are ephemeral and what problem each storage abstraction solves
- Use `emptyDir` for scratch space and `hostPath` for node-local access (and know why to avoid the latter in production)
- Understand the PersistentVolume / PersistentVolumeClaim / StorageClass relationship
- Provision storage both statically (by hand) and dynamically (via a StorageClass)
- Understand access modes and reclaim policies
- Observe what happens to persistent data across Pod restarts vs. Pod deletion

## 1. Concepts

### 1.1 Anatomy of a minimal PersistentVolumeClaim

`pvc-local-path.yaml` is about as minimal as a *useful* PVC gets — every field earns its place:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: hello-pvc
spec:
  accessModes:
    - ReadWriteOnce      # how many Nodes may mount it at once — see §1.4
  storageClassName: local-path   # WHICH provisioner manufactures the storage — k3s's built-in default
  resources:
    requests:
      storage: 1Gi          # how much space to request
```

Four fields, no more: a name, an access mode, a `storageClassName`, and a size. There's deliberately no `hostPath`/disk path anywhere in this file — that's the whole point of the PVC abstraction (§1.3): the claim describes *what you need*, never *where it physically lives*.

### 1.2 The problem: containers forget everything

Recall from Day 1: a container's writable layer is thrown away when the container is removed. In Kubernetes this is worse than in plain Docker — a Pod can be rescheduled to a **different Node entirely** after a crash, a drain, or a rolling update, so even "the same disk on the same machine" isn't guaranteed unless you explicitly ask for it. Kubernetes gives you four escalating storage abstractions to match how long you need data to live and how widely it needs to be visible:

| Abstraction | Lifetime | Tied to a specific Node? | Typical use |
|---|---|---|---|
| Container filesystem | Single container's life | N/A | Nothing you care about |
| [`emptyDir`](https://kubernetes.io/docs/concepts/storage/volumes/#emptydir) | Pod's life (survives container restarts within the Pod, not Pod deletion) | Yes, implicitly (wherever the Pod lands) | Scratch space, cache, sharing files between containers in one Pod |
| [`hostPath`](https://kubernetes.io/docs/concepts/storage/volumes/#hostpath) | Node's life (outlives the Pod) | **Yes, explicitly** — the Pod must land back on that exact Node to see the same data | Node-level agents (log collectors, CNI plugins) — rarely appropriate for application data |
| [PersistentVolume (PV) / PersistentVolumeClaim (PVC)](https://kubernetes.io/docs/concepts/storage/persistent-volumes/) | Independent of any Pod or Node — as long as you want | No (backed by network storage, or dynamically provisioned local storage abstracted behind the claim) | Databases, uploaded files, anything that must survive a Pod being rescheduled anywhere in the cluster |

### 1.3 The PV / PVC / StorageClass model

This is the part that confuses newcomers most, so hold onto the analogy: **a PersistentVolume is a slab of actual storage; a PersistentVolumeClaim is a request for some storage matching certain criteria; a StorageClass is a recipe a provisioner uses to manufacture a PV on demand when a PVC asks for one.**

```
 StorageClass "local-path"          (the recipe / provisioner config)
        │
        │  a PVC asks for 1Gi, class "local-path"
        ▼
 PersistentVolumeClaim  ───bound to───▶  PersistentVolume  ───backed by───▶  actual disk
   (namespaced,                            (cluster-scoped,
    what your Pod                           the real storage
    references)                             resource)
        ▲
        │ Pod mounts the PVC (not the PV directly)
        │
      Pod
```

- **Static provisioning**: a cluster admin manually creates PV objects ahead of time (`pv-static.yaml` does this). A PVC that matches (capacity, access mode, storage class) gets bound to one automatically by the control plane.
- **Dynamic provisioning** (the common case today, and what you'll use almost everywhere in this course): a PVC references a **StorageClass**; a provisioner controller watching for unbound PVCs of that class creates a brand-new PV to satisfy it, on the spot. k3s ships a default StorageClass called [`local-path`](https://github.com/rancher/local-path-provisioner) that creates a directory on the Node's disk per PVC — good enough for this whole course, not suitable for production HA (it's tied to one Node, just like `hostPath`, underneath).

A Pod never references a PV directly — it references a **PVC** by name, and the PVC is already bound to whatever PV backs it. This indirection is what lets the same Pod spec work unchanged whether the underlying storage is a k3s local directory, an AWS EBS volume, or a Ceph cluster.

### 1.4 Access modes

| Mode | Meaning |
|---|---|
| `ReadWriteOnce` (RWO) | Mountable read-write by Pods on **one Node at a time** (as of recent Kubernetes versions, technically multiple Pods on the *same* node can share it — but never across Nodes) |
| `ReadOnlyMany` (ROX) | Mountable read-only by many Nodes simultaneously |
| `ReadWriteMany` (RWX) | Mountable read-write by many Nodes simultaneously — requires a storage backend that supports it (NFS, many cloud file services); `local-path` does **not** support this |
| `ReadWriteOncePod` (RWOP) | Like RWO, but enforces exactly one **Pod** cluster-wide, not just one Node — for workloads that must never have two writers even briefly during a rolling update |

### 1.5 Reclaim policy

When a PVC is deleted, what happens to its PV and the underlying data is controlled by `persistentVolumeReclaimPolicy`:
- `Delete` (default for dynamically-provisioned volumes) — the PV and its backing storage are deleted too.
- `Retain` — the PV (and data) survive PVC deletion, but the PV becomes `Released` and must be manually cleaned up or re-bound by an admin before reuse. Use this for anything you cannot afford to lose to a mistaken `kubectl delete`.

### Official documentation
- [Storage overview](https://kubernetes.io/docs/concepts/storage/)
- [Volumes](https://kubernetes.io/docs/concepts/storage/volumes/)
- [Persistent Volumes](https://kubernetes.io/docs/concepts/storage/persistent-volumes/)
- [Storage Classes](https://kubernetes.io/docs/concepts/storage/storage-classes/)
- [Dynamic Volume Provisioning](https://kubernetes.io/docs/concepts/storage/dynamic-provisioning/)
- [Configure a Pod to Use a PersistentVolume for Storage](https://kubernetes.io/docs/tasks/configure-pod-container/configure-persistent-volume-storage/)
- [k3s: local-path-provisioner](https://docs.k3s.io/storage)

## 2. Hands-on lab

```bash
cd day07-storage-and-volumes/manifests

# 2.1 The absolute minimum
kubectl apply -f pvc-local-path.yaml
kubectl get pvc hello-pvc          # STATUS: Bound within a few seconds
kubectl delete -f pvc-local-path.yaml

# 2.2 emptyDir — survives container restart, not Pod deletion
kubectl apply -f pod-emptydir.yaml
kubectl exec emptydir-demo -- cat /data/log.txt
kubectl exec emptydir-demo -- sh -c 'kill 1'     # crash the container; kubelet restarts it (same Pod)
sleep 2
kubectl exec emptydir-demo -- cat /data/log.txt   # unchanged data, container restarted around it
kubectl delete -f pod-emptydir.yaml               # deleting the POD destroys the emptyDir permanently

# 2.3 hostPath — tied to the node, survives Pod deletion
kubectl apply -f pod-hostpath.yaml
kubectl exec hostpath-demo -- cat /data/hostpath-log.txt
kubectl delete -f pod-hostpath.yaml
cat /tmp/k8s-hostpath-demo/hostpath-log.txt   # still there on the node's own disk!
rm -rf /tmp/k8s-hostpath-demo

# 2.4 Inspect the default StorageClass
kubectl get storageclass
kubectl describe storageclass local-path

# 2.5 Dynamic provisioning via PVC
kubectl apply -f pvc-local-path.yaml
kubectl get pvc hello-pvc -w        # watch STATUS go Pending -> Bound
kubectl get pv                      # a PV was created FOR you — note its name
kubectl describe pvc hello-pvc

# 2.6 Use the PVC from a Pod, and prove data survives Pod deletion
kubectl apply -f pod-with-pvc.yaml
kubectl exec pvc-demo -- cat /data/persistent-log.txt
kubectl delete pod pvc-demo
kubectl apply -f pod-with-pvc.yaml   # a NEW pod, same name, same PVC
kubectl exec pvc-demo -- cat /data/persistent-log.txt   # two lines now — data survived!

# 2.7 Static provisioning
sudo mkdir -p /mnt/static-pv-demo && sudo chmod 777 /mnt/static-pv-demo
kubectl apply -f pv-static.yaml
kubectl get pv,pvc
kubectl describe pv static-pv-demo   # Status: Bound, Claim: default/static-pvc-demo

# 2.8 Clean up
kubectl delete -f pod-with-pvc.yaml -f pvc-local-path.yaml -f pv-static.yaml
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| PVC stuck `STATUS: Pending` forever | No `StorageClass` matches what's requested (typo'd name, or none installed), or a static PV's capacity/access-mode doesn't satisfy the claim | `kubectl describe pvc <name>` for the exact reason; `kubectl get storageclass` to confirm what's actually available (k3s's default is `local-path`) |
| Pod stuck `ContainerCreating`, `describe pod` mentions `FailedMount` or `FailedAttachVolume` | The PV/PVC hasn't finished binding yet, or (multi-node) the volume is already attached elsewhere | `kubectl get pvc` to confirm `Bound` status first — a Pod can't mount an unbound claim |
| `Multi-Attach error for volume ... Volume is already exclusively attached to one node` | A `ReadWriteOnce` volume is already in use by a Pod on a different Node | Confirm you need RWX instead, or ensure only one Pod uses that PVC at a time (Day 8's per-replica PVC pattern avoids this entirely) |
| Deleted a PVC and the data (and PV) vanished immediately, unexpectedly | Default `persistentVolumeReclaimPolicy` for dynamically-provisioned volumes is `Delete`, not `Retain` (section 1.4) | Check `kubectl get pv <name> -o jsonpath='{.spec.persistentVolumeReclaimPolicy}'` *before* deleting anything you care about |
| `kubectl delete pv <name>` seems to hang, PV stuck `Terminating` | The `kubernetes.io/pv-protection` finalizer blocks deletion while it's still `Bound` to a live PVC | Delete the PVC (and any Pod using it) first; the PV finalizer clears automatically once nothing references it |

See also: [Debugging Common Kubernetes Issues](../TROUBLESHOOTING.md).

## 3. Key commands reference

| Command | Purpose |
|---|---|
| `kubectl get pv,pvc` | List PersistentVolumes and PersistentVolumeClaims |
| `kubectl get storageclass` (`sc` short name) | List available StorageClasses; `(default)` marks the implicit one |
| `kubectl describe pvc <name>` | See binding status and any provisioning errors in Events |
| `kubectl describe pv <name>` | See reclaim policy, capacity, and which PVC (if any) it's bound to |

Next: [Day 8 — StatefulSets](../day08-statefulsets/README.md)
