# Day 17 — Pod Security Standards, Admission Control & Image Supply-Chain Basics

## Learning objectives
- Enforce `securityContext` rules cluster-wide with Pod Security Standards, instead of trusting every manifest
- Understand the request lifecycle through admission control (mutating and validating)
- Write a `ValidatingAdmissionPolicy` using CEL, with no webhook server to run
- Apply basic image supply-chain hygiene: tags vs. digests, `imagePullPolicy`, and where signing fits in
- Read a Pod Security Standard rejection message and fix the violation

## 1. Concepts

### 1.1 From "hope everyone sets securityContext correctly" to enforcement

Day 16 taught you to *write* a hardened `securityContext`. Nothing so far stops a teammate from applying a Pod with `privileged: true` tomorrow. [**Pod Security Standards (PSS)**](https://kubernetes.io/docs/concepts/security/pod-security-standards/) define three increasingly strict policy levels, and the built-in **PodSecurity admission controller** enforces them automatically, per namespace, via **labels on the Namespace object itself** — no separate policy CRD, no webhook to run.

| Level | What it allows |
|---|---|
| `privileged` | Unrestricted — the (lack of a) policy, for trusted infrastructure namespaces only |
| `baseline` | Blocks known privilege-escalation vectors (`privileged: true`, host namespaces, dangerous capabilities) but doesn't require non-root or restrict much else |
| `restricted` | Heavily hardened: requires `runAsNonRoot`, blocks privilege escalation, requires dropping all capabilities (adding back only a small allowed set), requires a seccomp profile — essentially, requires everything `pod-securitycontext.yaml` demonstrated in Day 16 |

Each namespace can set independent labels for three **modes**:
- `enforce` — actually reject non-compliant Pods.
- `warn` — allow them, but return a client-visible warning (great for a "coming soon" rollout).
- `audit` — allow them, but record a violation in the audit log, with no user-visible warning.

This is why real migrations typically go `audit` → `warn` → `enforce`, over time, rather than flipping straight to `enforce` and breaking everyone's existing workloads at once.

### 1.2 Where this fits: the full admission control pipeline

Every write request to the API server passes through, **in this order**, after authentication and RBAC authorization succeed:

```
 Request ──▶ Authentication ──▶ Authorization (RBAC) ──▶ Mutating admission ──▶ Schema validation ──▶ Validating admission ──▶ etcd
                                                          (can MODIFY the object,       │              (can only ALLOW/DENY,
                                                           e.g. inject a sidecar,        │               e.g. PodSecurity,
                                                           default a field)              │               ValidatingAdmissionPolicy)
                                                                                          ▼
                                                                              rejected here = malformed object,
                                                                              never reaches admission at all
```

[**Admission controllers**](https://kubernetes.io/docs/reference/access-control/admission-controllers/) are the pluggable hook points at the two admission stages. Kubernetes ships several **built-in** ones compiled into `kube-apiserver` (`PodSecurity`, `ResourceQuota` and `LimitRanger` from Day 10, `ServiceAccount`, and more — `kube-apiserver --help` lists what's enabled), and supports two **extensible, user-defined** mechanisms for custom rules:

- **Admission webhooks** (`MutatingWebhookConfiguration`/`ValidatingWebhookConfiguration`) — the API server calls out over HTTPS to an external service you write and run yourself, which returns an allow/deny (and, for mutating, an optional patch). Maximally flexible, but you must build, deploy, secure, and keep highly available a webhook server that sits in the critical path of *every* matching write to the cluster.
- **`ValidatingAdmissionPolicy`** (GA since Kubernetes 1.30) — write the same kind of validation rule as an in-process [CEL (Common Expression Language)](https://kubernetes.io/docs/reference/using-api/cel/) expression evaluated **directly inside `kube-apiserver`**, no external service at all. Faster, simpler to operate, and sufficient for most straightforward "reject objects that don't satisfy this rule" needs — exactly what today's lab uses.

### 1.3 Image supply-chain basics

The image you deploy is itself an attack surface, independent of everything above:

- **Tags are mutable, digests are not.** `hello-k8s:1.0.0` can be re-pushed tomorrow pointing at completely different content with the exact same tag — nothing prevents this. A **digest** (`hello-k8s@sha256:abcd1234...`) is a cryptographic hash of the exact image content — pinning to a digest guarantees you get byte-for-byte the same image every time, which matters enormously for reproducible deploys and incident forensics ("which exact image was running when this happened?").
- **`:latest` is worse than a normal mutable tag** — it's the *default* when no tag is specified at all, actively invites accidental staleness, and today's lab policy specifically blocks it.
- **`imagePullPolicy`** controls when the kubelet re-checks the registry: `Always` (re-verify every time, safest but slower/chattier), `IfNotPresent` (default for non-`:latest` tags — trust whatever's cached locally), `Never` (only ever use what's already cached — used for fully air-gapped/pre-loaded images). Note Kubernetes silently forces `Always` whenever the tag is `:latest`, precisely because that tag is expected to change.
- **Signing and provenance** (out of scope to fully implement in this lab, but know it exists): tools like [Sigstore/cosign](https://docs.sigstore.dev/) let you cryptographically sign images at build time and verify that signature at admission time (often via an admission webhook or a policy engine like Kyverno/OPA Gatekeeper), so the cluster can refuse to run any image that wasn't built by your trusted CI pipeline — the natural next step beyond today's simpler tag-hygiene rule.

### Official documentation
- [Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)
- [Enforce Pod Security Standards with Namespace Labels](https://kubernetes.io/docs/tasks/configure-pod-container/enforce-standards-namespace-labels/)
- [Admission Controllers Reference](https://kubernetes.io/docs/reference/access-control/admission-controllers/)
- [Validating Admission Policy](https://kubernetes.io/docs/reference/access-control/validating-admission-policy/)
- [CEL in Kubernetes](https://kubernetes.io/docs/reference/using-api/cel/)
- [Dynamic Admission Control (webhooks)](https://kubernetes.io/docs/reference/access-control/extensible-admission-controllers/)
- [Images (imagePullPolicy, digests)](https://kubernetes.io/docs/concepts/containers/images/)
- [Sigstore / cosign documentation](https://docs.sigstore.dev/)

## 2. Hands-on lab

```bash
cd day17-pod-security-and-admission/manifests

# 2.1 Create namespaces at different enforcement levels
kubectl apply -f namespace-baseline.yaml
kubectl apply -f namespace-restricted.yaml

# 2.2 A privileged Pod is rejected outright by "restricted"
kubectl apply -f pod-noncompliant.yaml
# Error from server (Forbidden): ... violates PodSecurity "restricted:latest":
#   privileged (container "hello-k8s" must not set securityContext.privileged=true),
#   allowPrivilegeEscalation != false ...
# READ EVERY LINE — it lists every single violation found, not just the first

# 2.3 The same Pod is FINE under "baseline" (a weaker standard)
kubectl apply -f pod-noncompliant.yaml -n baseline-ns   # succeeds — baseline doesn't require non-root etc.
kubectl delete pod noncompliant-pod -n baseline-ns

# 2.4 A fully compliant Pod succeeds under "restricted"
kubectl apply -f pod-compliant.yaml
kubectl get pod compliant-pod -n restricted-ns

# 2.5 warn/audit mode preview: switch restricted-ns to warn-only
kubectl label namespace restricted-ns pod-security.kubernetes.io/enforce-
kubectl label namespace restricted-ns pod-security.kubernetes.io/enforce=privileged --overwrite
kubectl apply -f pod-noncompliant.yaml   # now SUCCEEDS, but check the client output for a Warning line
kubectl delete pod noncompliant-pod -n restricted-ns
kubectl label namespace restricted-ns pod-security.kubernetes.io/enforce=restricted --overwrite

# 2.6 ValidatingAdmissionPolicy: block :latest images with CEL
kubectl apply -f validatingadmissionpolicy.yaml
kubectl run bad-tag --image=nginx:latest -n restricted-ns
# denied by validating admission policy 'no-latest-tag-policy' ...
kubectl run good-tag --image=nginx:1.27-alpine -n restricted-ns   # succeeds

# 2.7 Clean up
kubectl delete -f .
kubectl delete namespace baseline-ns restricted-ns
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Pod rejected with `violates PodSecurity "restricted:latest"` and a list of reasons | The namespace enforces the `restricted` standard and the Pod's `securityContext` doesn't satisfy every requirement | `describe` output lists **every** violation in one pass — fix them together rather than one at a time; see Day 17's own worked example |
| Same Pod works fine in one namespace but is rejected in another | Different namespaces can enforce different Pod Security Standard levels via their own labels | `kubectl get namespace <ns> --show-labels` to see which level (`privileged`/`baseline`/`restricted`) actually applies there |
| Applied a `ValidatingAdmissionPolicy`, but non-compliant objects still get created | `validationActions` is set to `Warn` or `Audit`, not `Deny` — this only surfaces a warning, it never blocks | Check the `ValidatingAdmissionPolicyBinding`'s `validationActions` field |
| A CEL expression in a policy always evaluates as if the field were missing | Used a bare `object.spec.foo` reference on an optional field without `has()` first — CEL errors (or short-circuits unexpectedly) on unset optional fields | Guard optional field access with `has(object.spec.foo)` before referencing its value |
| Pod Security warning appears in `kubectl` output, but the Pod is still created | That's `warn` mode working exactly as designed — it's non-blocking by definition, meant for migration periods (section 1.1) | If you actually want it blocked, the namespace needs `enforce`, not just `warn`, at that level |

See also: [Debugging Common Kubernetes Issues](../TROUBLESHOOTING.md).

## 3. Key commands reference

| Command | Purpose |
|---|---|
| `kubectl label namespace <ns> pod-security.kubernetes.io/enforce=<level>` | Set/change a namespace's enforced PSS level |
| `kubectl get validatingadmissionpolicy,validatingadmissionpolicybinding` | Inspect active CEL-based policies |
| `kubectl get pods -n <ns> -o jsonpath='{.items[*].spec.containers[*].image}'` | Quick audit of image references in use |
| `kubectl api-resources \| grep admission` | List admission-related API resources available in your cluster version |

Next: [Day 18 — Observability](../day18-observability/README.md)
