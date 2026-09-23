---
---
# Day 21 — Exercises

## Exercise 1 — Write the minimal HPA from scratch
Without looking at `hpa-minimal.yaml`, write an HPA named `scratch-hpa` targeting the `php-apache` Deployment (from `hpa-app.yaml`), scaling between 1 and 4 replicas on 60% average CPU utilization. Apply it and confirm `kubectl get hpa scratch-hpa` shows a real percentage under `TARGETS` within a minute (not `<unknown>`). Delete it afterward.

[→ solution](SOLUTIONS.md#exercise-1)

## Exercise 2 — Tighten the target and observe more aggressive scaling
Change `hpa.yaml`'s `averageUtilization` from `50` to `20` and reapply. Repeat the load test from section 2.3. Does it scale out further (closer to `maxReplicas`) for the same load than before? Explain why, referencing the HPA formula in section 1.1.

[→ solution](SOLUTIONS.md#exercise-2)

## Exercise 3 — Hit maxReplicas
With the load generator running, watch `kubectl get hpa php-apache -w` until replicas plateau at `maxReplicas: 6` despite CPU usage remaining well above target. What does `kubectl describe hpa` say about why it won't scale further? What real-world capacity-planning conversation does hitting `maxReplicas` under real sustained load usually trigger?

[→ solution](SOLUTIONS.md#exercise-3)

## Exercise 4 — Multiple metrics
Add a second metric to `hpa.yaml`'s `metrics` list targeting `memory` at `averageUtilization: 70`, alongside the existing CPU metric. Read the docs on how HPA behaves with multiple metrics (hint: it doesn't average them) and explain, in your own words, which replica count wins when different metrics suggest different desired replica counts.

[→ solution](SOLUTIONS.md#exercise-4)

## Exercise 5 — Blue-green: verify green BEFORE cutover
Redo the blue-green lab, but this time verify `green`'s content directly — before touching the Service at all — using `kubectl port-forward` targeting a specific green Pod by name (not the Service). Only after confirming it responds correctly, perform the selector cutover. Explain why this "verify in isolation, then cut over atomically" order is the entire safety value of blue-green, compared to just applying `bluegreen-green.yaml` as a normal rolling update over `blue` directly.

[→ solution](SOLUTIONS.md#exercise-5)

## Exercise 6 — Canary rollback
With the canary lab running, simulate discovering a bug in the canary: immediately scale `hello-canary-canary` to `0` replicas. Re-run the same 20-request loop from section 2.6 and confirm 100% of traffic now goes to `STABLE`. How fast was this "rollback" compared to a `kubectl rollout undo` on a RollingUpdate Deployment that had already progressed partway through its rollout?

[→ solution](SOLUTIONS.md#exercise-6)

## Exercise 7 (stretch) — Read (not run) a VPA recommendation manifest
Without installing VPA (too heavy for this lab, per section 1.2), read the [VPA `VerticalPodAutoscaler` CRD example](https://github.com/kubernetes/autoscaler/blob/master/vertical-pod-autoscaler/examples/hamster.yaml) in the project's GitHub repo. Write down, in your own words: what `updateMode: "Off"` means in practice for a team just starting to adopt VPA, and why a team would deliberately choose to run VPA in `Off` mode for weeks before ever switching to `Auto` on a production workload.

[→ solution](SOLUTIONS.md#exercise-7)
