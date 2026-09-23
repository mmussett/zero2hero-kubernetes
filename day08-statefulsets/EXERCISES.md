---
---
# Day 8 — Exercises

## Exercise 1 — Write the minimal StatefulSet from scratch
Without looking at `statefulset-minimal.yaml`, write a headless Service AND a StatefulSet, both named `scratch-sts`, running `localhost:5000/hello-k8s:1.0.0` with `replicas: 2`. Apply both, confirm you get Pods named `scratch-sts-0` and `scratch-sts-1` (not random suffixes), then delete both.

[→ solution](SOLUTIONS.md#exercise-1)

## Exercise 2 — Convert to a Deployment and compare
Copy `statefulset.yaml` into a Deployment with `replicas: 3` (drop `serviceName`, `volumeClaimTemplates`, and `podManagementPolicy`; add a plain `emptyDir` volume instead so it still runs). Apply both side by side under different names and compare `kubectl get pods` output. What's different about the Pod names, and what would happen to `identity.txt`'s content if you deleted one Pod from each?

[→ solution](SOLUTIONS.md#exercise-2)

## Exercise 3 — Why StatefulSets never auto-delete PVCs
After scaling `hello-stateful` down to 1 replica (section 2.5), the PVCs for `-1` and `-2` are still present even though no Pod uses them. Read the [StatefulSet docs section on PersistentVolumeClaim retention](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/#persistentvolumeclaim-retention) and explain, in your own words, the data-safety reasoning behind this default — then look up the `persistentVolumeClaimRetentionPolicy` field that (in recent Kubernetes versions) lets you opt into automatic deletion, and write the YAML snippet that would enable it.

[→ solution](SOLUTIONS.md#exercise-3)

## Exercise 4 — Ordered startup dependency
Modify the `record-identity` init container to `sleep 15` before writing its file. Apply the StatefulSet fresh and time how long it takes all 3 Pods to become Ready. Explain why the total time is roughly 3× a single Pod's startup time rather than all three starting in parallel, and which field you'd change to make them start concurrently instead.

[→ solution](SOLUTIONS.md#exercise-4)

## Exercise 5 — Break the headless Service requirement
Create a copy of `statefulset.yaml` named `broken-sts.yaml` with `serviceName: does-not-exist` (a Service that doesn't exist). Apply it. Does the StatefulSet controller refuse to create Pods, or do they start anyway? What specifically stops working as a result (test with `nslookup` from a netshoot Pod)?

[→ solution](SOLUTIONS.md#exercise-5)

## Exercise 6 (stretch) — Manual failover simulation
Delete `hello-stateful-0` specifically (not scale down — just delete that one Pod) while the other two keep running. Watch `kubectl get pods -w` — does `-1` or `-2` get touched at all? What does this tell you about the blast radius of a single replica failure in a StatefulSet compared to a Deployment losing one Pod?

[→ solution](SOLUTIONS.md#exercise-6)
