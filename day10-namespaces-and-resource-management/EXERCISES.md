---
---
# Day 10 — Exercises

## Exercise 1 — Write the minimal Namespace and ResourceQuota from scratch
Without looking at `namespace-minimal.yaml`/`resourcequota-minimal.yaml`, create a Namespace named `scratch-ns` and a ResourceQuota in it named `scratch-quota` capping `pods` at `3`. Try creating 4 bare Pods (`kubectl run p1 --image=busybox:1.36 -n scratch-ns -- sleep 3600`, etc.) and confirm the 4th is rejected. Clean up the namespace afterward (deletes everything inside it).

[→ solution](SOLUTIONS.md#exercise-1)

## Exercise 2 — Same name, different namespaces
In both `default` and `team-alpha` namespaces, create a Pod named `twin` running `localhost:5000/hello-k8s:1.0.0`. Confirm both succeed with `kubectl get pods -A | grep twin`. What would have happened if you'd tried to create a second `twin` Pod in the *same* namespace?

[→ solution](SOLUTIONS.md#exercise-2)

## Exercise 3 — Exceed the Pod count quota
`team-alpha-quota` caps `pods: "10"`. Write a Deployment with `replicas: 15` in `team-alpha` using minimal resource requests that fit comfortably within the CPU/memory quota. Apply it and confirm via `kubectl get pods -n team-alpha | wc -l` and `kubectl describe resourcequota` that it stops at 10, not 15. What do the Pending/unscheduled replicas' Events say?

[→ solution](SOLUTIONS.md#exercise-3)

## Exercise 4 — LimitRange rejection
Try to create a Pod in `team-alpha` with an explicit `resources.limits.memory: 1Gi` (above the LimitRange's `max: 512Mi`). Record the exact admission error. Then try one with `resources.requests.cpu: 10m` (below the `min: 50m`) and record that error too.

[→ solution](SOLUTIONS.md#exercise-4)

## Exercise 5 — Guaranteed vs. BestEffort eviction priority
Create two Pods in `default`: `guaranteed-pod` with `requests.memory == limits.memory == 100Mi`, and `besteffort-pod` with no resources block at all, both running `busybox:1.36 sleep 3600`. Confirm their QoS classes with `kubectl get pod -o jsonpath='{.status.qosClass}'`. Explain, referencing section 1.4, which one the kubelet would kill first under real memory pressure, and why that ordering makes operational sense.

[→ solution](SOLUTIONS.md#exercise-5)

## Exercise 6 — NoExecute eviction
Repeat the taint exercise from the lab, but use `effect: NoExecute` instead of `NoSchedule`, and taint the node *while* `tolerating-pod`-style (non-tolerating) Pods are already running on it. What happens to already-running Pods that don't tolerate the taint — does `NoSchedule` do the same thing? Look up `tolerationSeconds` and explain what problem it solves.

[→ solution](SOLUTIONS.md#exercise-6)

## Exercise 7 (stretch) — Combine taint + affinity for a "dedicated pool" pattern
Using both a taint (`workload=batch:NoSchedule`) and a matching toleration + `nodeAffinity` requiring `workload=batch`, configure a Pod that will run **only** on nodes explicitly reserved for batch work, and confirm ordinary Pods (with no toleration) cannot land there while your batch Pod also cannot land on an unlabeled node. Explain why using affinity ALONE (without the taint) would be insufficient to keep other teams' Pods off this node.

[→ solution](SOLUTIONS.md#exercise-7)
