# Day 3 — Solutions

## Exercise 1
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: scratch-pod
spec:
  containers:
    - name: scratch-pod
      image: localhost:5000/hello-k8s:1.0.0
```
```bash
kubectl apply -f scratch-pod.yaml
kubectl get pod scratch-pod -w   # ctrl-c once Running
kubectl exec scratch-pod -- curl -s localhost:8080/
kubectl delete -f scratch-pod.yaml
```
No `ports`, `env`, `resources`, or probes needed — the app still runs and responds because it's the image's own `ENV PORT=8080` and `CMD` doing the work, not anything declared in the Pod spec (exactly the same lesson Day 4's `ports` field teaches for Deployments).

## Exercise 2
```yaml
# my-first-pod.yaml
apiVersion: v1
kind: Pod
metadata:
  name: my-first-pod
spec:
  containers:
    - name: hello-k8s
      image: localhost:5000/hello-k8s:1.0.0
      ports:
        - containerPort: 8080
      env:
        - name: GREETING
          value: "Exercise One"
      resources:
        requests:
          cpu: "100m"
        limits:
          cpu: "200m"
```
```bash
kubectl apply -f my-first-pod.yaml
kubectl port-forward pod/my-first-pod 8080:8080 &
curl localhost:8080/
kill %1
kubectl delete -f my-first-pod.yaml
```

## Exercise 3
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: bad-readiness
spec:
  containers:
    - name: hello-k8s
      image: localhost:5000/hello-k8s:1.0.0
      readinessProbe:
        httpGet:
          path: /does-not-exist
          port: 8080
        periodSeconds: 3
```
```bash
kubectl apply -f bad-readiness.yaml
kubectl describe pod bad-readiness
```
Events show repeating `Warning  Unhealthy  ... Readiness probe failed: HTTP probe failed with statuscode: 404`. `kubectl get pods` shows `READY 0/1` indefinitely, and `STATUS` stays `Running` — the container is alive and healthy, it's just never marked ready, so a Service would never route traffic to it. This is the key distinction from liveness failures: the container is never restarted.

```bash
kubectl delete -f bad-readiness.yaml
```

## Exercise 4
```bash
kubectl apply -f pod-crashloop.yaml
kubectl get pod crash-demo -w
```
Typical pattern: restart 1 happens almost immediately (~2s, matching the `sleep 2` in the command), then the gap roughly doubles each subsequent restart (~10s, ~20s, ~40s...) up to a cap (default max backoff 5 minutes). This is **exponential backoff**, and it protects the cluster (specifically the kubelet, the container runtime, and anything the crashing app talks to, like a database) from a tight crash loop hammering resources or a downstream dependency thousands of times a minute.

```bash
kubectl delete -f pod-crashloop.yaml
```

## Exercise 5
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: init-demo
spec:
  volumes:
    - name: config-vol
      emptyDir: {}
  initContainers:
    - name: fetch-config
      image: busybox:1.36
      command: ["sh", "-c", "echo 'ready=true' > /work/config.txt"]
      volumeMounts: [{name: config-vol, mountPath: /work}]
    - name: second-init
      image: busybox:1.36
      command: ["sh", "-c", "echo 'second=done' >> /work/config.txt && cat /work/config.txt"]
      volumeMounts: [{name: config-vol, mountPath: /work}]
  containers:
    - name: app
      image: busybox:1.36
      command: ["sh", "-c", "cat /work/config.txt && sleep 3600"]
      volumeMounts: [{name: config-vol, mountPath: /work}]
```
```bash
kubectl apply -f init-demo-2.yaml
kubectl get pod init-demo -w   # Init:0/2 -> Init:1/2 -> PodInitializing -> Running
kubectl logs init-demo -c second-init   # shows both lines, proving fetch-config already ran
```
`initContainers` run strictly one at a time, in list order; each must exit `0` before the next starts, and all must complete before any app container starts. This is the mechanism `Init:1/2` in `kubectl get pods` is reporting.

## Exercise 6
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: oom-demo
spec:
  containers:
    - name: stress
      image: polinux/stress
      command: ["stress"]
      args: ["--vm", "1", "--vm-bytes", "100M", "--vm-hang", "0"]
      resources:
        requests: {memory: "20Mi"}
        limits: {memory: "20Mi"}
```
```bash
kubectl apply -f oom-demo.yaml
kubectl describe pod oom-demo
```
Look at `status.containerStatuses[0].lastState.terminated` (via `describe`, shown as `Last State: Terminated, Reason: OOMKilled, Exit Code: 137`). `kubectl get pods` will show a climbing `RESTARTS` count as the kubelet keeps restarting it per `restartPolicy: Always`.

```bash
kubectl delete -f oom-demo.yaml
```

## Exercise 7
```bash
kubectl apply -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata: {name: crash-never}
spec:
  restartPolicy: Never
  containers: [{name: crasher, image: busybox:1.36, command: ["sh","-c","exit 1"]}]
---
apiVersion: v1
kind: Pod
metadata: {name: crash-onfailure}
spec:
  restartPolicy: OnFailure
  containers: [{name: crasher, image: busybox:1.36, command: ["sh","-c","exit 1"]}]
---
apiVersion: v1
kind: Pod
metadata: {name: crash-always}
spec:
  restartPolicy: Always
  containers: [{name: crasher, image: busybox:1.36, command: ["sh","-c","exit 1"]}]
EOF
sleep 30
kubectl get pods
```
Expected:
- `crash-never` — `STATUS: Error`, `RESTARTS: 0`. kubelet never restarts a `Never`-policy container.
- `crash-onfailure` — `STATUS: CrashLoopBackOff` (or `Running`→cycling), `RESTARTS` climbing. Restarted because it fails, backing off.
- `crash-always` — same restart behavior as `OnFailure` here, because the container *does* fail — `Always` restarts regardless of exit code (success or failure), `OnFailure` only restarts on non-zero exit. The visible difference between these two only appears when the container exits **successfully** (`exit 0`): `Always` would still restart it; `OnFailure` would leave it `Completed` and stop.

```bash
kubectl delete pod crash-never crash-onfailure crash-always
```
