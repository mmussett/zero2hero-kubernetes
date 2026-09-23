---
---
# Day 16 — RBAC, ServiceAccounts & SecurityContexts

## Learning objectives
- Explain the four-object RBAC model and when to use namespaced vs. cluster-scoped variants
- Grant a workload exactly the API permissions it needs, and no more
- Understand ServiceAccounts as the identity a Pod uses to talk to the API server
- Use `kubectl auth can-i` to test permissions without guessing
- Harden a Pod's runtime privileges with `securityContext`

## 1. Concepts

### 1.1 Anatomy of a minimal Role + RoleBinding + ServiceAccount

`serviceaccount.yaml` and `role-and-binding.yaml` together are the smallest useful RBAC setup — three objects, each about as small as it gets:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: pod-reader-sa
  namespace: default
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: pod-reader
  namespace: default
rules:
  - apiGroups: [""]                       # "" = the core API group
    resources: ["pods"]
    verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: pod-reader-binding
  namespace: default
subjects:
  - kind: ServiceAccount
    name: pod-reader-sa
    namespace: default
roleRef:
  kind: Role
  name: pod-reader
  apiGroup: rbac.authorization.k8s.io
```

A `ServiceAccount` has almost no fields at all — it's just a name to hang permissions off of. A `Role`'s `rules` is a list of `{apiGroups, resources, verbs}` triples — read it as "on these resource types, in these API groups, allow these verbs." A `RoleBinding` is the glue: `subjects` (who) + `roleRef` (what) in one object, nothing else. Every RBAC setup in this course, however elaborate, is built from exactly these three shapes repeated — never a fourth kind of field.

### 1.2 Two separate questions: authentication and authorization

Every request to `kube-apiserver` answers two questions in order: **"who are you?"** (authentication — a client cert, a token, etc.) and **"are you allowed to do this?"** (authorization). [**RBAC (Role-Based Access Control)**](https://kubernetes.io/docs/reference/access-control/rbac/) is Kubernetes's built-in authorization mechanism, and it's the one you'll configure constantly. It never answers "who are you" — that's handled separately (for humans, typically via your cloud provider or an OIDC integration; for workloads, via ServiceAccounts, section 1.4).

### 1.3 The four RBAC objects

```
   Role / ClusterRole            RoleBinding / ClusterRoleBinding
   "WHAT is allowed"      ──▶    "WHO gets that Role, and WHERE"
   (a list of rules:                    (links a subject — User,
    verbs on resources)                  Group, or ServiceAccount —
                                          to a Role/ClusterRole)
```

| Object | Scope | Purpose |
|---|---|---|
| `Role` | One namespace | Defines permissions (verbs like `get`/`list`/`watch`/`create`/`update`/`delete` on resources like `pods`, `deployments`) — cannot grant access to cluster-scoped resources (Nodes, Namespaces, PVs) |
| `ClusterRole` | Cluster-wide *definition* (its binding decides actual scope) | Same shape as Role, but **can** grant permissions on cluster-scoped resources, and can be reused across many namespaces via multiple RoleBindings |
| `RoleBinding` | One namespace | Grants a Role **or** a ClusterRole to a subject, but only within this binding's namespace |
| `ClusterRoleBinding` | Cluster-wide | Grants a ClusterRole to a subject across **every** namespace |

A common, easy-to-miss pattern: a `ClusterRole` bound via a namespaced `RoleBinding` grants those permissions **only in that namespace** — this is how platform teams define one reusable "developer" ClusterRole once, then grant it per-team, per-namespace, without duplicating the rule list.

### 1.4 ServiceAccounts — identity for workloads, not humans

A [**ServiceAccount**](https://kubernetes.io/docs/concepts/security/service-accounts/) is an identity a **Pod** authenticates to the API server as — the "who are you" for workloads specifically (humans use a different mechanism, typically external identity federated by the cluster admin, out of scope for a single-cluster training lab). Every namespace gets a `default` ServiceAccount automatically, and **every Pod uses it automatically unless `spec.serviceAccountName` says otherwise** — this is why, by default, `kubectl exec`-ing into almost any Pod and trying to call the API from inside it fails: the `default` ServiceAccount is deliberately granted zero permissions beyond authenticating.

kubelet auto-mounts that ServiceAccount's token into every Pod at `/var/run/secrets/kubernetes.io/serviceaccount/token` — any process inside the container can use it to call the API server directly, which is exactly what `kubectl` running inside a Pod, or any Operator (Day 22), does. This is also a real attack surface: if an attacker gains code execution in a Pod, they inherit whatever that Pod's ServiceAccount can do — one more reason to grant the narrowest permissions possible (see `automountServiceAccountToken: false` in the exercises for Pods that don't need API access at all).

### 1.5 SecurityContext — constraining what a container can do at runtime

Where RBAC controls what a Pod's *identity* can do **against the Kubernetes API**, [`securityContext`](https://kubernetes.io/docs/tasks/configure-pod-container/security-context/) controls what the container process itself can do **at the OS/kernel level** — a completely separate axis of security. Key fields, settable at Pod level (default for all containers) and overridable per-Container:

| Field | Effect |
|---|---|
| `runAsUser` / `runAsGroup` | Which UID/GID the container process runs as (recall Day 1's non-root Dockerfile discussion) |
| `runAsNonRoot: true` | Kubernetes **refuses to start** the container if it would run as UID 0, even if the image's own `USER` isn't set correctly — a backstop against a bad image |
| `readOnlyRootFilesystem: true` | The container's root filesystem is mounted read-only; only explicitly mounted volumes (e.g. an `emptyDir` at `/tmp`) are writable — dramatically limits what a compromised process can persist or modify |
| `allowPrivilegeEscalation: false` | Blocks a process from gaining more privileges than its parent (e.g. via setuid binaries) |
| `capabilities.drop: ["ALL"]` | Strips all Linux capabilities (fine-grained root privileges like binding low ports, changing file ownership) by default — add back only the specific ones actually needed via `capabilities.add` |
| `privileged: true` | The nuclear opt-out — full access to the host's devices and kernel capabilities, equivalent to root on the Node itself. Avoid entirely except for specific infrastructure Pods (some CNI/storage agents) that genuinely require it |

Day 17 builds on this directly with **Pod Security Standards**, which let a cluster admin *enforce* these settings namespace-wide instead of trusting every manifest author to set them correctly by hand.

### Official documentation
- [Using RBAC Authorization](https://kubernetes.io/docs/reference/access-control/rbac/)
- [Managing Service Accounts](https://kubernetes.io/docs/reference/access-control/service-accounts-admin/)
- [Configure Service Accounts for Pods](https://kubernetes.io/docs/tasks/configure-pod-container/configure-service-account/)
- [Configure a Security Context for a Pod or Container](https://kubernetes.io/docs/tasks/configure-pod-container/security-context/)
- [Linux Capabilities](https://kubernetes.io/docs/tasks/configure-pod-container/security-context/#set-capabilities-for-a-container)
- [kubectl auth can-i](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_auth/kubectl_auth_can-i/)

## 2. Hands-on lab

```bash
cd day16-rbac-and-service-accounts/manifests

# 2.1 The absolute minimum
kubectl apply -f serviceaccount.yaml
kubectl apply -f role-and-binding.yaml
kubectl auth can-i list pods --as=system:serviceaccount:default:pod-reader-sa
kubectl delete -f role-and-binding.yaml -f serviceaccount.yaml

# 2.2 Prove the default ServiceAccount has no permissions
kubectl apply -f pod-with-sa.yaml
kubectl wait --for=condition=ready pod/api-caller-default-sa --timeout=30s
kubectl exec api-caller-default-sa -- kubectl get pods
# Error: pods is forbidden: User "system:serviceaccount:default:default" cannot list resource "pods"

# 2.3 Create a ServiceAccount + Role + RoleBinding, then retry
kubectl apply -f serviceaccount.yaml
kubectl apply -f role-and-binding.yaml
kubectl wait --for=condition=ready pod/api-caller --timeout=30s
kubectl exec api-caller -- kubectl get pods           # works now
kubectl exec api-caller -- kubectl get deployments     # still forbidden — Role only grants "pods"
kubectl exec api-caller -- kubectl get nodes            # forbidden — cluster-scoped, no Role can grant this

# 2.4 ClusterRole + ClusterRoleBinding for cluster-scoped resources
kubectl apply -f clusterrole-and-binding.yaml
kubectl exec api-caller -- kubectl get nodes    # works now

# 2.5 Test permissions WITHOUT trial-and-error, using can-i
kubectl auth can-i list pods --as=system:serviceaccount:default:pod-reader-sa
kubectl auth can-i delete pods --as=system:serviceaccount:default:pod-reader-sa
kubectl auth can-i list nodes --as=system:serviceaccount:default:pod-reader-sa
kubectl auth can-i --list --as=system:serviceaccount:default:pod-reader-sa

# 2.6 SecurityContext: hardened vs. default
kubectl apply -f pod-securitycontext.yaml
kubectl exec secure-pod -- id                       # uid=10001, not root
kubectl exec secure-pod -- sh -c "touch /test.txt"   # fails — read-only root filesystem
kubectl exec secure-pod -- sh -c "touch /tmp/test.txt && echo ok"   # works — writable emptyDir

# 2.7 The over-privileged contrast (for awareness only — this is what NOT to do)
kubectl apply -f pod-privileged-bad.yaml
kubectl exec insecure-pod -- id   # uid=0 — full root, and privileged: true grants far more than that

# 2.8 Clean up
kubectl delete -f .
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Error from server (Forbidden): ... cannot list resource "X"` | Missing (or wrong) `Role`/`RoleBinding` granting that verb+resource to that subject | `kubectl auth can-i <verb> <resource> --as=<subject> -n <namespace>` to test before guessing |
| A `kubectl` command run **inside a Pod** gets `Forbidden`, but works fine from your own terminal | The Pod is authenticating as its **ServiceAccount** (default: the namespace's `default` SA, which has zero permissions), not as you | Create a dedicated ServiceAccount with a Role/RoleBinding granting exactly what that workload needs |
| Granted a `ClusterRole` via a `RoleBinding`, but it only works in one namespace | That's expected — a `RoleBinding` scopes a `ClusterRole`'s permissions to its own namespace only; a `ClusterRoleBinding` is what makes it cluster-wide (Day 16 §1.2) | Use a `ClusterRoleBinding` if you genuinely need cluster-wide access, otherwise this is working as intended |
| Tried to grant a permission you don't have yourself, and it silently failed / was rejected | RBAC's escalation-prevention rule blocks a subject from granting permissions it doesn't already possess | Grant it as a more privileged user/subject, or confirm the granting subject already has that permission itself |
| `automountServiceAccountToken: false` set, but a Pod still seems to have API access | Check whether the container is instead using **credentials baked into the image or env vars** rather than the mounted token — a completely separate access path | Audit the image/config for hardcoded credentials if disabling the token mount didn't change observed behavior |

See also: [Debugging Common Kubernetes Issues](../TROUBLESHOOTING.md).

## 3. Key commands reference

| Command | Purpose |
|---|---|
| `kubectl auth can-i <verb> <resource> [--as=<subject>] [-n ns]` | Test a permission without trial-and-error |
| `kubectl auth can-i --list [--as=<subject>]` | List every permission a subject has |
| `kubectl get role,rolebinding,clusterrole,clusterrolebinding` | Inventory RBAC objects |
| `kubectl describe role <name>` / `kubectl describe clusterrole <name>` | See exactly which rules a Role grants |
| `kubectl exec <pod> -- id` | Confirm the actual runtime UID/GID a container is running as |

Next: [Day 17 — Pod Security Standards & Admission Control](../day17-pod-security-and-admission/README.md)
