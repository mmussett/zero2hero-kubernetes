---
---
# Day 17 — Solutions

## Exercise 1
Original rejection typically lists 3 distinct violations at once:
```
violates PodSecurity "restricted:latest":
  privileged (container "hello-k8s" must not set securityContext.privileged=true),
  allowPrivilegeEscalation != false (container "hello-k8s" must set securityContext.allowPrivilegeEscalation=false),
  unrestricted capabilities (container "hello-k8s" must set securityContext.capabilities.drop=["ALL"]),
  runAsNonRoot != true (pod or container "hello-k8s" must set securityContext.runAsNonRoot=true),
  seccompProfile (pod or container "hello-k8s" must set securityContext.seccompProfile.type to "RuntimeDefault" or "Localhost")
```
(Exact count is typically 5 once you include the implicit `runAsNonRoot` and `seccompProfile` requirements that apply even though the original manifest only explicitly set 2 fields — `restricted` requires several fields to be **explicitly present**, not just "not obviously dangerous.") Fixing them one at a time and reapplying shows the error list shrinking each time, confirming the admission controller reports **every** violation found in a single pass, not just the first — useful in practice so you don't have to iterate one-error-at-a-time in a real migration, though this exercise deliberately has you do so once to see the mechanism.

## Exercise 2
```bash
kubectl create namespace migrating-ns
kubectl label namespace migrating-ns pod-security.kubernetes.io/audit=restricted
sed 's/namespace: restricted-ns/namespace: migrating-ns/' pod-noncompliant.yaml | kubectl apply -f -
# succeeds silently — no client-visible warning at all
```
`audit` mode only writes to the **API server's audit log** (a server-side JSON event stream, configured via `--audit-log-path`/`--audit-policy-file` on `kube-apiserver`) — it is invisible to the `kubectl` client entirely. k3s does not enable API server audit logging by default (it requires explicitly passing `--kube-apiserver-arg=audit-log-path=... --kube-apiserver-arg=audit-policy-file=...` at install time); in a production cluster (EKS/GKE/AKS or a properly configured kubeadm cluster), this audit trail typically flows into the cloud provider's centralized logging service or a self-hosted log aggregator, and is exactly the kind of signal a security team reviews before flipping a namespace to `enforce`.
```bash
kubectl label namespace migrating-ns pod-security.kubernetes.io/warn=restricted
kubectl delete pod noncompliant-pod -n migrating-ns --ignore-not-found
sed 's/namespace: restricted-ns/namespace: migrating-ns/' pod-noncompliant.yaml | kubectl apply -f -
```
This time `kubectl` prints `Warning: would violate PodSecurity "restricted:latest": ...` to stderr, but the Pod is still created — this three-stage rollout (`audit` → `warn` → `enforce`) lets a team retroactively discover *every* non-compliant workload across a namespace over days/weeks (via audit logs and visible warnings surfacing in CI/deploy tooling) before anything is actually blocked, dramatically lowering the risk of a surprise production outage from flipping straight to `enforce`.

## Exercise 3
```yaml
validations:
  - expression: "object.spec.containers.all(c, c.image.contains(':') && !c.image.endsWith(':latest'))"
    message: "Container images must specify a non-'latest' tag."
  - expression: "has(object.metadata.labels) && has(object.metadata.labels.team)"
    message: "Pods must have a 'team' label for cost/ownership attribution."
```
```bash
kubectl apply -f vap-with-team-label.yaml
kubectl run no-team-pod --image=nginx:1.27-alpine -n restricted-ns
```
Rejected, with the response specifically quoting the **second** `message` (`Pods must have a 'team' label...`), even though the image tag itself was compliant — proving each `validations` entry is checked and reported independently, which is essential for giving developers an actionable, specific error rather than one generic "denied" message covering multiple unrelated rules.

## Exercise 4
```yaml
spec:
  validationActions: ["Warn"]
```
```bash
kubectl apply -f vap-binding-warn.yaml
kubectl run bad-tag-warn --image=nginx:latest -n restricted-ns
```
The Pod is **created successfully** this time — `Warn` never blocks the request, it only causes `kube-apiserver` to attach a `Warning:` response header that `kubectl` renders to the user (e.g. `Warning: ... no-latest-tag-policy ... Container images must specify a non-'latest' tag.`). `Warn` is the right choice while you're first rolling out a **new, not-yet-fully-trusted** policy across an existing cluster with workloads you haven't fully audited — it surfaces every violation to whoever's applying manifests (ideally feeding into CI output too) without risking an unexpected production outage from a policy that turns out to have an edge case or false positive you didn't anticipate; you graduate to `Deny` once you've observed a clean warning period with no unexpected hits.
```bash
kubectl delete pod bad-tag-warn -n restricted-ns
```

## Exercise 5
```bash
docker push localhost:5000/hello-k8s:1.0.0
DIGEST=$(docker inspect --format='{{index .RepoDigests 0}}' localhost:5000/hello-k8s:1.0.0)
kubectl run digest-pod --image="$DIGEST" -n restricted-ns --overrides='{"spec":{"securityContext":{"runAsNonRoot":true,"runAsUser":10001,"seccompProfile":{"type":"RuntimeDefault"}},"containers":[{"name":"digest-pod","image":"'"$DIGEST"'","securityContext":{"allowPrivilegeEscalation":false,"capabilities":{"drop":["ALL"]}}}]}}'
kubectl get pod digest-pod -n restricted-ns
```
Now rebuild `app.py` with a visibly different response message, then:
```bash
cd ../../day01-containers-and-docker/app
docker build -t localhost:5000/hello-k8s:1.0.0 .
docker push localhost:5000/hello-k8s:1.0.0
```
`digest-pod` (already running, referencing the **old** digest explicitly) is completely unaffected — it keeps running the exact original image content forever, since a digest reference can never silently repoint. A **new** Pod created referencing the tag `1.0.0` (not the digest) and pulled fresh, however, gets the **new** content, because the tag `1.0.0` in the registry now points at the newly-pushed image — the tag itself was mutated. This is the exact, concrete proof of section 1.3's claim: tags are a mutable pointer, digests are an immutable, content-addressed reference — anything that must guarantee "the exact same bits every time" (reproducible deploys, compliance/forensics, disaster recovery re-deploys) should reference images by digest, not tag, in production.

## Exercise 6
```yaml
apiVersion: admissionregistration.k8s.io/v1
kind: ValidatingAdmissionPolicy
metadata: {name: no-host-namespaces}
spec:
  failurePolicy: Fail
  matchConstraints:
    resourceRules:
      - apiGroups: [""]
        apiVersions: ["v1"]
        operations: ["CREATE", "UPDATE"]
        resources: ["pods"]
  validations:
    - expression: >-
        (!has(object.spec.hostNetwork) || object.spec.hostNetwork == false) &&
        (!has(object.spec.hostPID) || object.spec.hostPID == false) &&
        (!has(object.spec.hostIPC) || object.spec.hostIPC == false)
      message: "Pods may not use hostNetwork, hostPID, or hostIPC."
---
apiVersion: admissionregistration.k8s.io/v1
kind: ValidatingAdmissionPolicyBinding
metadata: {name: no-host-namespaces-binding}
spec:
  policyName: no-host-namespaces
  validationActions: ["Deny"]
  matchResources:
    namespaceSelector:
      matchLabels: {kubernetes.io/metadata.name: restricted-ns}
```
```bash
kubectl apply -f no-host-namespaces.yaml
kubectl run host-pid-test --image=busybox:1.36 -n restricted-ns --overrides='{"spec":{"hostPID":true,"containers":[{"name":"host-pid-test","image":"busybox:1.36","command":["sleep","3600"]}]}}'
# denied by validating admission policy 'no-host-namespaces'
```
The real `baseline` standard additionally restricts (among others, and non-exhaustively): dangerous `securityContext.capabilities.add` values beyond a small allow-list (`AUDIT_WRITE`, `CHOWN`, etc.), `hostPath` volume types entirely, `hostPort` usage, disallowed `/proc` mount types, non-default AppArmor/SELinux options, and Sysctls outside a safe allow-list. A hand-rolled policy covering only the three host-namespace flags is a reasonable learning exercise, but this comparison itself is the real lesson: reimplementing PSS by hand is easy to get subtly incomplete — which is precisely why Kubernetes ships `baseline`/`restricted` as maintained, versioned, built-in standards rather than expecting every cluster operator to hand-write and maintain an equivalent policy set themselves.
