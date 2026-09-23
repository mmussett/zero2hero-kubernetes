---
---
# Day 3 — Exercises

## Exercise 1 — Write the minimal Pod from scratch
Without looking at `pod-minimal.yaml`, write a brand-new Pod manifest named `scratch-pod` running `localhost:5000/hello-k8s:1.0.0`. Apply it, confirm it reaches `Running`, `kubectl exec` a `curl` against it to prove the app responds, then delete it. Four fields matter: `kind`, `metadata.name`, and the one container's `name` and `image` — nothing else is required for a valid Pod.

[→ solution](SOLUTIONS.md#exercise-1)

## Exercise 2 — Write a Pod manifest from scratch
Without copying `pod-basic.yaml`, write a new Pod manifest named `my-first-pod.yaml` that runs `localhost:5000/hello-k8s:1.0.0`, sets the env var `GREETING=Exercise One`, exposes container port `8080`, and sets CPU request `100m` / limit `200m`. Apply it and `curl` it via port-forward.

[→ solution](SOLUTIONS.md#exercise-2)

## Exercise 3 — Diagnose a failing readiness probe
Create a Pod using `localhost:5000/hello-k8s:1.0.0` with a `readinessProbe` pointing at the wrong path (`/does-not-exist`). Apply it, then use `kubectl describe` to find the exact reason the Pod never becomes `Ready`. What does `kubectl get pods` show in the `READY` column while this is happening?

[→ solution](SOLUTIONS.md#exercise-3)

## Exercise 4 — CrashLoopBackOff timing
Apply `pod-crashloop.yaml` and, using `kubectl get pod crash-demo -w`, record the wall-clock gap between the first three restarts. What pattern do you observe, and what is this backoff mechanism protecting the cluster from?

[→ solution](SOLUTIONS.md#exercise-4)

## Exercise 5 — Init container ordering
Modify `pod-initcontainer.yaml` to add a **second** init container named `second-init` that runs after `fetch-config` and appends a line to the same file. Prove via `kubectl logs init-demo -c second-init` that it ran after the first, and that they ran sequentially (not in parallel).

[→ solution](SOLUTIONS.md#exercise-5)

## Exercise 6 — Resource limit enforcement
Create a Pod requesting `memory: 20Mi` with limit `memory: 20Mi`, running `polinux/stress` with `stress --vm 1 --vm-bytes 100M --vm-hang 0` as the command. Confirm via `kubectl describe pod` that it was OOMKilled, and explain what field in the Pod status shows this.

[→ solution](SOLUTIONS.md#exercise-6)

## Exercise 7 (stretch) — restartPolicy behavior
Create three Pods identical to `pod-crashloop.yaml` except with `restartPolicy: Never`, `OnFailure`, and `Always` respectively (three separate Pod names). After 30 seconds, compare `kubectl get pods` output for all three. Explain the difference you observe.

[→ solution](SOLUTIONS.md#exercise-7)
