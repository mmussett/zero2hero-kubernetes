---
---
# Day 6 — Solutions

## Exercise 1
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: scratch-config
data:
  MODE: "demo"
```
```bash
kubectl apply -f scratch-config.yaml
kubectl get configmap scratch-config -o yaml
kubectl delete -f scratch-config.yaml
```
`data` is the only required field beyond the standard `apiVersion`/`kind`/`metadata.name` — a ConfigMap has no `spec` at all, unlike almost everything else in this course.

## Exercise 2
```bash
mkdir nginx-conf
cat <<'EOF' > nginx-conf/default.conf
server {
    listen 80;
    location / { return 200 "ok\n"; }
}
EOF
kubectl create configmap nginx-conf --from-file=nginx-conf/ --dry-run=client -o yaml
```
`kubectl` names the key after the **filename** (`default.conf`), and the value is the **entire file content** as a multi-line string — identical in shape to the `app.properties` key in `configmap-literal.yaml`. This is the standard way to ship whole config files (nginx configs, `application.yaml`, etc.) into a cluster from files that already exist in a repo.

## Exercise 3
```yaml
apiVersion: v1
kind: Pod
metadata: {name: hello-selective-env}
spec:
  containers:
    - name: hello-k8s
      image: localhost:5000/hello-k8s:1.0.0
      env:
        - name: MY_GREETING
          valueFrom:
            configMapKeyRef:
              name: hello-config
              key: GREETING
```
```bash
kubectl apply -f selective-env.yaml
kubectl exec hello-selective-env -- printenv | grep MY_GREETING
# MY_GREETING=Hello from a ConfigMap!
kubectl exec hello-selective-env -- printenv | grep -c APP_VERSION   # 0 — not injected
```
`env.valueFrom.configMapKeyRef` pulls exactly one key and lets you rename it on the way in; `envFrom` is all-or-nothing but keeps original key names (with an optional shared `prefix:`).

## Exercise 4
```bash
echo "placeholder-cert-content" > tls.crt
echo "placeholder-key-content" > tls.key
kubectl create secret tls hello-tls --cert=tls.crt --key=tls.key
kubectl get secret hello-tls -o yaml
```
The two data keys are `tls.crt` and `tls.key` — this exact shape (`type: kubernetes.io/tls` with those two keys) is what Ingress resources (Day 11) expect when you reference a Secret for TLS termination.

## Exercise 5
```yaml
apiVersion: v1
kind: ConfigMap
metadata: {name: hello-config-immutable}
immutable: true
data:
  GREETING: "cannot change me"
```
```bash
kubectl apply -f immutable-cm.yaml
kubectl patch configmap hello-config-immutable --type merge -p '{"data":{"GREETING":"new"}}'
```
Error: `ConfigMap "hello-config-immutable" is invalid: data: Forbidden: field is immutable when \`immutable\` is set`. (To change it you must delete and recreate, or — better — create a new ConfigMap and update the Pod template to reference it, following the same "new object per change" pattern a Deployment uses for rollouts.)

Performance reason: the kubelet on every Node watches every mounted ConfigMap/Secret for changes so it can update the mounted files live. At cluster scale (thousands of ConfigMaps, thousands of Nodes), that watch load on `kube-apiserver` is significant. Marking a ConfigMap `immutable: true` tells the kubelet it never needs to watch that object again, which materially reduces `kube-apiserver` load in large clusters — this is a documented, deliberate scalability optimization, not just a safety feature.

## Exercise 6
```bash
kubectl apply -f pod-env-from.yaml
kubectl exec hello-envfrom -- sh -c "cat /proc/1/environ | tr '\0' '\n' | grep DB_PASSWORD"
# DB_PASSWORD=s3cr3t-pass   <- plainly visible

kubectl apply -f pod-volume-mount.yaml
kubectl exec hello-volumes -- sh -c "cat /proc/1/environ | tr '\0' '\n' | grep -i secret"
# (no output)
```
This proves environment variables are visible to **anything that can read `/proc/<pid>/environ` for that process** — any process in the same container, any debugging tool, any crash-dump/core-dump mechanism, and often third-party APM/monitoring agents that enumerate process environments by design. A mounted Secret file is only readable to whatever the file's Unix permissions (`defaultMode: 0400` in `pod-volume-mount.yaml`) allow — a materially smaller blast radius. This is why security-conscious teams standardize on volume-mounted Secrets over env-var Secrets for anything sensitive, despite env vars being more convenient to wire up.
