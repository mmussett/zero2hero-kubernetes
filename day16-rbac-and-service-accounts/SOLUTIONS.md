# Day 16 — Solutions

## Exercise 1
```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: scratch-sa
  namespace: default
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: scratch-role
  namespace: default
rules:
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: scratch-binding
  namespace: default
subjects:
  - kind: ServiceAccount
    name: scratch-sa
    namespace: default
roleRef:
  kind: Role
  name: scratch-role
  apiGroup: rbac.authorization.k8s.io
```
```bash
kubectl apply -f scratch-rbac.yaml
kubectl auth can-i list pods --as=system:serviceaccount:default:scratch-sa     # yes
kubectl auth can-i delete pods --as=system:serviceaccount:default:scratch-sa   # no
kubectl delete -f scratch-rbac.yaml
```
Exactly the three shapes from section 1.1, nothing more — the `verbs` list is the only thing that changed to make this narrower than the course's own `pod-reader` example.

## Exercise 2
```yaml
apiVersion: v1
kind: ServiceAccount
metadata: {name: pod-writer-sa, namespace: default}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata: {name: pod-writer, namespace: default}
rules:
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata: {name: pod-writer-binding, namespace: default}
subjects: [{kind: ServiceAccount, name: pod-writer-sa, namespace: default}]
roleRef: {kind: Role, name: pod-writer, apiGroup: rbac.authorization.k8s.io}
```
```bash
kubectl apply -f pod-writer-rbac.yaml
kubectl run test-victim --image=busybox:1.36 -- sleep 3600
kubectl run api-caller-writer --image=bitnami/kubectl:1.30 --overrides='{"spec":{"serviceAccountName":"pod-writer-sa"}}' -- sleep 3600
kubectl wait --for=condition=ready pod/api-caller-writer --timeout=30s
kubectl exec api-caller-writer -- kubectl delete pod test-victim    # succeeds
kubectl exec api-caller-writer -- kubectl get nodes                 # still forbidden
```

## Exercise 3
```bash
kubectl create serviceaccount viewer-sa
kubectl create rolebinding viewer-binding --clusterrole=view --serviceaccount=default:viewer-sa -n default
kubectl auth can-i get pods --as=system:serviceaccount:default:viewer-sa -n default        # yes
kubectl auth can-i get pods --as=system:serviceaccount:default:viewer-sa -n kube-system    # no
```
The `view` ClusterRole's **rules** are identical everywhere — it's a single object, cluster-wide by definition — but a `RoleBinding` (as opposed to a `ClusterRoleBinding`) only grants those rules **within the namespace the RoleBinding itself lives in**. This is the single most useful RBAC pattern for multi-tenant clusters: define broad, reusable ClusterRoles once (`view`, `edit`, `admin` are all built in), then grant them scoped per-team via namespaced RoleBindings, never a ClusterRoleBinding, so Team A's `view` grant never leaks into Team B's namespace.

## Exercise 4
```yaml
apiVersion: v1
kind: Pod
metadata: {name: no-token-pod}
spec:
  automountServiceAccountToken: false
  containers:
    - {name: app, image: busybox:1.36, command: ["sleep", "3600"]}
```
```bash
kubectl apply -f no-token-pod.yaml
kubectl exec no-token-pod -- ls /var/run/secrets/kubernetes.io/serviceaccount/
# ls: /var/run/secrets/kubernetes.io/serviceaccount/: No such file or directory
```
You'd want this even for a ServiceAccount **with** real permissions on any Pod that never calls the Kubernetes API itself — a plain web server, a batch worker, a database. Leaving the token mounted by default on Pods that don't need it needlessly expands the blast radius of a container compromise: an attacker with code execution in that Pod, who would otherwise have no reason to touch the Kubernetes API at all, gains a live, usable credential purely because it happened to be sitting on disk unused. Many security benchmarks (including CIS Kubernetes Benchmark) flag `automountServiceAccountToken: true` on API-inert workloads as an unnecessary risk for exactly this reason.

## Exercise 5
```bash
kubectl create clusterrolebinding escalation-attempt \
  --clusterrole=cluster-admin \
  --serviceaccount=default:pod-reader-sa \
  --as=system:serviceaccount:default:pod-reader-sa
```
Error: `clusterrolebindings.rbac.authorization.k8s.io is forbidden: User "system:serviceaccount:default:pod-reader-sa" cannot create resource "clusterrolebindings"` (or, if `pod-reader-sa` *could* create ClusterRoleBindings but lacked `cluster-admin`'s actual rules itself, RBAC's **escalation prevention** rule blocks it anyway: *a subject can never use `create`/`update` on Role/ClusterRole/RoleBinding/ClusterRoleBinding objects to grant permissions it does not already possess itself* — checked automatically by the `RBAC` authorizer, not something you have to configure). This closes an obvious privilege-escalation hole: without it, any subject with permission to create RoleBindings could trivially grant itself `cluster-admin` regardless of what rules it actually started with.

## Exercise 6
```bash
kubectl apply -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata: {name: rofs-no-tmp}
spec:
  securityContext: {runAsUser: 10001, runAsNonRoot: true}
  containers:
    - name: hello-k8s
      image: localhost:5000/hello-k8s:1.0.0
      securityContext: {readOnlyRootFilesystem: true, capabilities: {drop: ["ALL"]}}
EOF
kubectl exec rofs-no-tmp -- python3 -c "open('/tmp/x','w').close()"
```
Fails: `OSError: [Errno 30] Read-only file system: '/tmp/x'` — with no volume mounted at `/tmp`, that path is part of the container's read-only root filesystem, and the write is rejected at the kernel level. This matters in practice because a huge fraction of real-world libraries and frameworks (logging libraries, `tempfile` in Python, many Java/JVM caches, some TLS libraries) write to `/tmp` or similar paths by default without the application developer necessarily realizing it — turning on `readOnlyRootFilesystem` for an app you didn't write yourself frequently surfaces surprise write failures. The general remediation pattern is exactly what `pod-securitycontext.yaml` does correctly: keep `readOnlyRootFilesystem: true` for security, but explicitly mount a small `emptyDir` (or similar) at every specific path the application legitimately needs to write to — narrowing writability to just those paths instead of either the whole filesystem or none of it.

## Exercise 7
```yaml
apiVersion: v1
kind: Pod
metadata: {name: netbind-demo}
spec:
  securityContext: {runAsUser: 10001, runAsNonRoot: true}
  containers:
    - name: hello-k8s
      image: localhost:5000/hello-k8s:1.0.0
      env: [{name: PORT, value: "80"}]
      ports: [{containerPort: 80}]
      securityContext:
        capabilities: {drop: ["ALL"], add: ["NET_BIND_SERVICE"]}
```
```bash
kubectl apply -f netbind-demo.yaml
kubectl exec netbind-demo -- id                 # uid=10001, still non-root
kubectl port-forward pod/netbind-demo 8080:80 &
curl localhost:8080/                             # works — bound port 80 as non-root
kill %1
```
Binding to ports below 1024 is normally restricted to root specifically via the `CAP_NET_BIND_SERVICE` Linux capability — historically the *only* practical way to allow it was running the whole process as root, which grants **every** other root capability too (changing file ownership arbitrarily, tracing/killing other processes, loading kernel modules if further unconfined, etc.). `capabilities.add: ["NET_BIND_SERVICE"]` on top of `drop: ["ALL"]` grants **exactly and only** that one narrow permission, to a process still running as an unprivileged UID with every other root capability explicitly stripped — if that process is compromised, the attacker gains nothing beyond "can bind low ports," an enormously smaller blast radius than full root or `privileged: true` (which additionally grants host device access, kernel capability access, and in most configurations an effective escape path to the underlying Node).
