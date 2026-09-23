# Day 16 — Exercises

## Exercise 1 — Write the minimal ServiceAccount + Role + RoleBinding from scratch
Without looking at `serviceaccount.yaml`/`role-and-binding.yaml`, write a ServiceAccount named `scratch-sa`, a Role named `scratch-role` granting `get`/`list` on `pods` only, and a RoleBinding connecting them — all in the `default` namespace. Apply all three and confirm with `kubectl auth can-i list pods --as=system:serviceaccount:default:scratch-sa` that it returns `yes`, while `kubectl auth can-i delete pods --as=system:serviceaccount:default:scratch-sa` returns `no`.

[→ solution](SOLUTIONS.md#exercise-1)

## Exercise 2 — Write a Role granting write access
Create a new Role, `pod-writer`, granting `create`, `update`, `patch`, and `delete` (in addition to `get`/`list`/`watch`) on `pods`, bound to a new ServiceAccount `pod-writer-sa` via a RoleBinding. From a Pod using that ServiceAccount, prove you can `kubectl delete pod <some-test-pod>` but still cannot `kubectl get nodes`.

[→ solution](SOLUTIONS.md#exercise-2)

## Exercise 3 — aggregate a ClusterRole to one namespace only
Using the built-in `view` ClusterRole (`kubectl get clusterrole view -o yaml` to inspect it — a broad, pre-defined read-only role Kubernetes ships), create a RoleBinding in the `default` namespace only, binding it to a new ServiceAccount `viewer-sa`. Confirm with `kubectl auth can-i get pods --as=system:serviceaccount:default:viewer-sa -n default` (yes) vs. `kubectl auth can-i get pods --as=system:serviceaccount:default:viewer-sa -n kube-system` (no) — even though the `view` ClusterRole itself is identical either way.

[→ solution](SOLUTIONS.md#exercise-3)

## Exercise 4 — automountServiceAccountToken: false
Create a Pod using the `default` ServiceAccount but with `automountServiceAccountToken: false` set at the Pod level. Exec into it and confirm `/var/run/secrets/kubernetes.io/serviceaccount/` doesn't exist at all (vs. a normal Pod, where it exists even for the permission-less `default` SA). Explain a concrete scenario where you'd want this set even for a Pod using a ServiceAccount that DOES have real permissions.

[→ solution](SOLUTIONS.md#exercise-4)

## Exercise 5 — Escalation prevention
Try to create a RoleBinding granting `pod-reader-sa` the built-in `cluster-admin` ClusterRole (cluster-wide, via a ClusterRoleBinding) **while authenticated as `pod-reader-sa` itself** (hint: `kubectl create clusterrolebinding ... --as=system:serviceaccount:default:pod-reader-sa`). What happens, and what RBAC rule (look up "privilege escalation prevention" in the docs) explains why a subject can never grant permissions it doesn't already itself possess?

[→ solution](SOLUTIONS.md#exercise-5)

## Exercise 6 — readOnlyRootFilesystem breaking an app
Take `pod-securitycontext.yaml`'s `secure-pod` and remove the `/tmp` `emptyDir` volume mount (keep `readOnlyRootFilesystem: true`). Reapply and try `kubectl exec secure-pod -- python -c "open('/tmp/x','w').close()"`. What fails, and why does this matter for real applications (many frameworks/libraries write temp files, cache files, or PID files by default)? What's the general remediation pattern?

[→ solution](SOLUTIONS.md#exercise-6)

## Exercise 7 (stretch) — Drop-then-add capabilities
Modify `pod-securitycontext.yaml` to `capabilities: {drop: ["ALL"], add: ["NET_BIND_SERVICE"]}`, and change the container to attempt binding to port 80 directly (rather than 8080) by setting `PORT=80` and updating `containerPort`. Confirm it can bind to port 80 (normally a privileged operation requiring root) *without* running as root at all. Explain why `capabilities.add` for one narrow capability is a far smaller security exposure than either running as root or setting `privileged: true`.

[→ solution](SOLUTIONS.md#exercise-7)
