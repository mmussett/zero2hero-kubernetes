---
---
# Day 6 — ConfigMaps & Secrets

## Learning objectives
- Externalize configuration from container images using ConfigMaps
- Understand what Secrets do and do not protect against
- Inject config as environment variables vs. mounted files, and know when to use each
- Understand live-update behavior of mounted config vs. env vars
- Generate ConfigMaps/Secrets imperatively from files and literals

## 1. Concepts

### 1.1 Anatomy of a minimal ConfigMap

`configmap-minimal.yaml` is the smallest valid ConfigMap that exists:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: hello-world-config
data:
  GREETING: "Hello, minimal world!"    # any number of key: value pairs go here
```

That's the whole shape — `data` is just a flat map of strings (or, as Day 6's other manifests show, whole file contents under one key). A Secret (below) is byte-for-byte the same shape, with `data` values base64-encoded instead of plain text — same API, different intent.

### 1.2 Why externalize config

The [twelve-factor app](https://12factor.net/config) principle: config that varies between environments (dev/staging/prod) must never be baked into the image. A [**ConfigMap**](https://kubernetes.io/docs/concepts/configuration/configmap/) holds non-sensitive key-value data or whole files; a [**Secret**](https://kubernetes.io/docs/concepts/configuration/secret/) holds the same shape of data but is intended for sensitive values (passwords, tokens, keys).

### 1.3 Secrets are not encrypted by default — know this cold

A Secret's `data` values are **base64-encoded**, not encrypted. Anyone with API read access to that Secret (or `etcd` access) can trivially recover the plaintext. What Secrets *do* give you over a ConfigMap:
- They're not printed in `kubectl describe` output by default (values are redacted; keys are shown).
- They can be size-limited and are held in `tmpfs` (memory-backed) when mounted as volumes, never written to a Node's disk.
- Kubernetes supports [encryption at rest for Secrets in etcd](https://kubernetes.io/docs/tasks/administer-cluster/encrypt-data/), but it must be explicitly configured by the cluster admin — it is **not on by default**, including in k3s.
- RBAC (Day 16) can restrict *who* can `get`/`list` Secrets separately from other resources.

For real production secrets (not this course's lab), use a dedicated secrets manager (Vault, cloud KMS-backed solutions, [External Secrets Operator](https://external-secrets.io/)) that injects secrets at runtime rather than storing them as Kubernetes API objects at all.

### 1.4 Env vars vs. volume mounts

| | Env var (`env`/`envFrom`) | Volume mount |
|---|---|---|
| Set at | Container start only | Continuously synced by kubelet |
| Updates on ConfigMap/Secret change | **No** — Pod must be restarted | **Yes** — file content updates in place (with a propagation delay of up to ~1 minute by default) |
| Good for | Simple values, 12-factor style | Whole config files, certs, anything an app hot-reloads |
| Visible in `/proc/<pid>/environ` | Yes (readable to anyone who can exec into the Pod) | No — regular file permissions apply |

## 2. Hands-on lab

```bash
cd day06-configmaps-and-secrets/manifests

# 2.1 The absolute minimum
kubectl apply -f configmap-minimal.yaml
kubectl get configmap hello-world-config -o yaml
kubectl delete -f configmap-minimal.yaml

# 2.2 Declarative ConfigMap + Secret
kubectl apply -f configmap-literal.yaml
kubectl apply -f secret-generic.yaml
kubectl get configmap hello-config -o yaml
kubectl get secret hello-db-secret -o yaml          # data is base64, not plaintext
kubectl get secret hello-db-secret -o jsonpath='{.data.DB_PASSWORD}' | base64 -d; echo

# 2.3 Imperative generation (common in scripts/CI)
kubectl create configmap hello-config-imp --from-literal=GREETING="Imperative hi" --dry-run=client -o yaml
kubectl create secret generic hello-secret-imp --from-literal=API_KEY=topsecret123 --dry-run=client -o yaml

# 2.4 Inject as environment variables
kubectl apply -f pod-env-from.yaml
kubectl exec hello-envfrom -- printenv | grep -E 'GREETING|APP_VERSION|DB_'
kubectl exec hello-envfrom -- curl -s localhost:8080/

# 2.5 Inject as mounted files
kubectl apply -f pod-volume-mount.yaml
kubectl exec hello-volumes -- cat /etc/config/GREETING
kubectl exec hello-volumes -- cat /etc/config/app.properties
kubectl exec hello-volumes -- ls -l /etc/secret/
kubectl exec hello-volumes -- cat /etc/secret/DB_PASSWORD; echo

# 2.6 Live-update behavior
kubectl patch configmap hello-config --type merge -p '{"data":{"GREETING":"Updated live!"}}'
sleep 65   # kubelet sync period
kubectl exec hello-volumes -- cat /etc/config/GREETING   # updated
kubectl exec hello-envfrom -- printenv | grep GREETING   # unchanged — env vars are frozen at start

# 2.7 Clean up
kubectl delete -f .
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Pod stuck, `Reason: CreateContainerConfigError` | `envFrom`/`env.valueFrom` or a volume references a ConfigMap/Secret (or a specific key within one) that doesn't exist | `kubectl describe pod` names the exact missing object/key; `kubectl get configmap,secret -n <ns>` to confirm what really exists |
| Changed a ConfigMap, but the running Pod's env var is still the old value | Env vars are frozen at container start — they never live-update, by design (section 1.4) | Restart the Pod (`kubectl rollout restart deployment/<name>`, or delete the bare Pod) to pick up the new value |
| Changed a ConfigMap, mounted as a volume, but the file still shows old content after a minute | kubelet's sync period hasn't elapsed yet, or the Pod reads the file once at startup instead of watching for changes | Wait a bit longer (up to ~60s by default), or confirm the app actually re-reads the file rather than caching it in memory |
| `kubectl get secret <name> -o yaml` shows what looks like garbage, not the real value | That's base64 **encoding**, not encryption — completely expected | `kubectl get secret <name> -o jsonpath='{.data.KEY}' \| base64 -d` |
| `kubectl create secret ... --from-literal` command works, but the app still can't read the value | Decoding is automatic when a Secret is consumed via `env`/volume — you never base64-decode it yourself in the Pod spec | Confirm you passed the *plaintext* value to `--from-literal`, not an already-base64'd string (a common double-encoding mistake) |

See also: [Debugging Common Kubernetes Issues](../TROUBLESHOOTING.md).

## 3. Key commands reference

| Command | Purpose |
|---|---|
| `kubectl create configmap <name> --from-literal=k=v` | Imperative ConfigMap from literals |
| `kubectl create configmap <name> --from-file=path/` | ConfigMap from every file in a directory |
| `kubectl create secret generic <name> --from-literal=k=v` | Imperative Secret |
| `kubectl get secret <name> -o jsonpath='{.data.KEY}' \| base64 -d` | Decode a Secret value |
| `kubectl patch configmap <name> --type merge -p '{"data":{...}}'` | In-place update |

### Official documentation
- [ConfigMaps](https://kubernetes.io/docs/concepts/configuration/configmap/)
- [Secrets](https://kubernetes.io/docs/concepts/configuration/secret/)
- [Distribute Credentials Securely Using Secrets](https://kubernetes.io/docs/tasks/inject-data-application/distribute-credentials-secure/)
- [Encrypting Confidential Data at Rest](https://kubernetes.io/docs/tasks/administer-cluster/encrypt-data/)
- [Configure a Pod to Use a ConfigMap](https://kubernetes.io/docs/tasks/configure-pod-container/configure-pod-configmap/)
- [The Twelve-Factor App: Config](https://12factor.net/config)

Next: [Day 7 — Storage, Volumes & Persistent Storage](../day07-storage-and-volumes/README.md)
