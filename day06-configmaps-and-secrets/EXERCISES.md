# Day 6 — Exercises

## Exercise 1 — Write the minimal ConfigMap from scratch
Without looking at `configmap-minimal.yaml`, write a ConfigMap named `scratch-config` with a single key `MODE` set to `demo`. Apply it and confirm with `kubectl get configmap scratch-config -o yaml` that the value round-trips exactly. Delete it afterward.

[→ solution](SOLUTIONS.md#exercise-1)

## Exercise 2 — from-file ConfigMap
Create a directory `nginx-conf/` containing a file `default.conf` with any valid minimal nginx server block. Generate a ConfigMap from that whole directory using `--from-file`. Inspect the resulting YAML — how did `kubectl` name the key, and what does the value contain?

[→ solution](SOLUTIONS.md#exercise-2)

## Exercise 3 — Selective key injection
Using `envFrom` injects *every* key. Instead, write a Pod manifest that injects **only** `GREETING` from `hello-config` as an env var named `MY_GREETING` (hint: `env:` + `valueFrom.configMapKeyRef`, not `envFrom`). Verify with `printenv`.

[→ solution](SOLUTIONS.md#exercise-3)

## Exercise 4 — Secret from a TLS-style file pair
Generate two throwaway files, `tls.crt` and `tls.key` (any placeholder text is fine — this is about the mechanism, not real certs), and create a Secret of type `kubernetes.io/tls` from them using `kubectl create secret tls`. Inspect it with `kubectl get secret <name> -o yaml` and identify the two data keys Kubernetes expects for this Secret type.

[→ solution](SOLUTIONS.md#exercise-4)

## Exercise 5 — Immutable ConfigMaps
Add `immutable: true` to a copy of `configmap-literal.yaml`, apply it, then try to `kubectl patch` a value in it. Record the exact error. Read the docs section on immutable ConfigMaps/Secrets and explain in one sentence the performance reason this feature exists at cluster scale.

[→ solution](SOLUTIONS.md#exercise-5)

## Exercise 6 (stretch) — Secret exposure via exec
Apply `pod-env-from.yaml`. `kubectl exec` into it and run `cat /proc/1/environ | tr '\0' '\n'`. Confirm `DB_PASSWORD` is plainly visible. Now compare against `pod-volume-mount.yaml`: exec in and try to find the secret value anywhere under `/proc/1/environ`. What does this prove about which injection method leaks secrets to anything with process-inspection access inside the same container?

[→ solution](SOLUTIONS.md#exercise-6)
