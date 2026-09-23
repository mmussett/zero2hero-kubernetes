---
---
# Day 7 — Exercises

## Exercise 1 — Write the minimal PVC from scratch
Without looking at `pvc-local-path.yaml`, write a PersistentVolumeClaim named `scratch-pvc` requesting `500Mi` with `ReadWriteOnce` access, using the `local-path` StorageClass. Apply it and confirm `kubectl get pvc scratch-pvc` reaches `STATUS: Bound` within a few seconds — with no PV manifest written by you anywhere. Delete it afterward.

[→ solution](SOLUTIONS.md#exercise-1)

## Exercise 2 — emptyDir is per-Pod, not per-container
Modify `pod-emptydir.yaml` to add a second container, `reader` (image `busybox:1.36`, command `sh -c "sleep 3600"`), mounting the same `scratch` volume at `/readonly-data`. Apply it, then `kubectl exec emptydir-demo -c reader -- cat /readonly-data/log.txt`. What does this prove about volume sharing within a single Pod?

[→ solution](SOLUTIONS.md#exercise-2)

## Exercise 3 — Reclaim policy in action
Apply `pvc-local-path.yaml` and `pod-with-pvc.yaml`, write some data, then delete **both** the Pod and the PVC (`kubectl delete pod pvc-demo pvc/hello-pvc`). Check `kubectl get pv` afterward — is the dynamically-provisioned PV still there? What is its default `persistentVolumeReclaimPolicy` (check with `kubectl get pv <name> -o jsonpath='{.spec.persistentVolumeReclaimPolicy}'` before you delete anything), and what does that tell you about data safety with dynamic provisioning by default?

[→ solution](SOLUTIONS.md#exercise-3)

## Exercise 4 — Capacity mismatch
Try to create a PVC requesting `storage: 10Gi` against the `manual` StorageClass used in `pv-static.yaml`, whose PV only offers `500Mi`. What state does the PVC sit in, and what does `kubectl describe pvc` tell you about why it never binds?

[→ solution](SOLUTIONS.md#exercise-4)

## Exercise 5 — ReadWriteOnce in practice
Create a Deployment (not a bare Pod) with 2 replicas, both mounting the **same** PVC (`hello-pvc` from `pvc-local-path.yaml`) at `/data`. Apply it and check `kubectl get pods` — do both replicas reach `Running`? Explain the result in terms of access modes and, since both Pods likely land on the same single node in this lab, note explicitly why a real multi-node cluster would behave differently.

[→ solution](SOLUTIONS.md#exercise-5)

## Exercise 6 — Delete a PV that's still bound
Try to `kubectl delete pv <name>` for the PV backing `hello-pvc` while the PVC and a Pod using it are still present. What happens — does it delete immediately? Look up `kubectl describe pv` for a `Finalizers` field and explain what it's protecting against.

[→ solution](SOLUTIONS.md#exercise-6)

## Exercise 7 (stretch) — Inspect where local-path actually stores data
Find the actual host directory `local-path-provisioner` created for your `hello-pvc` PV (hint: `kubectl get pv <name> -o yaml` shows a `hostPath` under `spec`, or check `/var/lib/rancher/k3s/storage/` on the node). `cat` the file directly from the node's filesystem, bypassing Kubernetes entirely, and confirm it matches what `kubectl exec` showed you. What does this prove about what "dynamic provisioning" is actually doing under the hood in k3s specifically (vs. a cloud-backed StorageClass)?

[→ solution](SOLUTIONS.md#exercise-7)
