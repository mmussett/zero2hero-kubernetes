---
---
# Day 4 — Exercises

## Exercise 1 — Write the minimal Deployment from scratch
Without looking at `deployment-minimal.yaml`, write a brand-new Deployment manifest named `scratch-test`, running `localhost:5000/hello-k8s:1.0.0`, with `replicas: 2`. Apply it, confirm two Pods come up and reach `Running`, then delete it. This exact shape — `apiVersion`, `kind`, `metadata.name`, `spec.replicas`, `spec.selector.matchLabels`, `spec.template.metadata.labels`, `spec.template.spec.containers[].name`/`.image` — is what you'll type from memory constantly for the rest of this course. There's no shortcut to knowing it cold; this exercise exists purely to make you type it once without a reference in front of you.

[→ solution](SOLUTIONS.md#exercise-1)

## Exercise 2 — Observe orphaned Pods
Apply `deployment-v1.yaml`. Find the ReplicaSet's name, then delete the **Deployment only** using `kubectl delete deployment hello-k8s --cascade=orphan`. Confirm the ReplicaSet and its Pods still exist. Explain what `--cascade=orphan` did differently from a normal delete, then clean up the orphaned ReplicaSet manually.

[→ solution](SOLUTIONS.md#exercise-2)

## Exercise 3 — maxUnavailable vs maxSurge in practice
Re-apply `deployment-v1.yaml` (3 replicas). Edit a copy of `deployment-v2.yaml` to set `maxSurge: 0, maxUnavailable: 1`, apply it, and in a second terminal run `kubectl get pods -l app=hello-k8s -w` during the rollout. Describe, in your own words, the difference in Pod count behavior compared to the course's default `maxSurge: 1, maxUnavailable: 0`.

[→ solution](SOLUTIONS.md#exercise-3)

## Exercise 4 — Roll back to a specific revision
Perform three sequential rollouts (v1 → v2 → bad), so you have at least 3 revisions in history. Use `kubectl rollout history deployment/hello-k8s` to list them, then roll back directly to revision 1 (not just "undo one step") using `--to-revision`. Verify the running image matches v1.

[→ solution](SOLUTIONS.md#exercise-4)

## Exercise 5 — Readiness gate during rollout
Modify `deployment-v2.yaml`'s readiness probe to point at `/does-not-exist`, apply it, and observe `kubectl rollout status`. Does the rollout ever complete? What does `kubectl get pods` show for the new ReplicaSet's Pods, and why does the Deployment refuse to terminate old Pods in this state?

[→ solution](SOLUTIONS.md#exercise-5)

## Exercise 6 (stretch) — Recreate strategy
Change `deployment-v1.yaml`'s `strategy.type` to `Recreate` (remove the `rollingUpdate` block entirely) and re-apply after changing the image tag. Watch `kubectl get pods -w` during the rollout. How does Pod count behave differently from `RollingUpdate`, and in what real-world scenario would you deliberately choose `Recreate` despite the downtime it causes?

[→ solution](SOLUTIONS.md#exercise-6)
