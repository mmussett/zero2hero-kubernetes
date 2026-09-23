---
---
# Day 2 — Solutions

## Exercise 1
Typical output includes:
- `coredns-...` — cluster DNS (Day 15), a k3s-bundled add-on, not core control plane
- `local-path-provisioner-...` — k3s's default dynamic storage provisioner (Day 7), an add-on
- `metrics-server-...` — powers `kubectl top` (Day 18), an add-on
- `traefik-...` (and `svclb-traefik-...`) — the bundled Ingress controller (Day 11), an add-on

Note that with k3s's default embedded SQLite datastore, `etcd`, `kube-apiserver`, `kube-scheduler`, and `kube-controller-manager` run as **child processes inside the single `k3s server` binary/process**, not as separate Pods — that's the "lightweight" part. `ps aux | grep k3s` on the host shows them; they will *not* appear in `kubectl get pods -A`. `kubelet` and `kube-proxy` similarly run inside the `k3s agent` process (or the same binary in single-node mode).

## Exercise 2
```bash
kubectl config view
kubectl config current-context   # e.g. "default"
kubectl --context=doesnotexist get nodes
```
Last command errors: `error: context "doesnotexist" does not exist`. This proves `kubectl` resolves everything (server URL + credentials) purely from local config *before* making any network call — nothing server-side is checked until a valid context is selected.

## Exercise 3
```bash
kubectl run broken --image=localhost:5000/does-not-exist:1.0.0
kubectl get pods
# broken   0/1   ErrImagePull   or ImagePullBackOff
kubectl describe pod broken
kubectl get events --sort-by=.lastTimestamp
```
`Reason: ErrImagePull` (then `ImagePullBackOff` once kubelet starts backing off retries), with an Event message like `Failed to pull image "localhost:5000/does-not-exist:1.0.0": ... manifest unknown`. This is the single most common early-course failure mode — always `describe` then `get events` before anything else.

```bash
kubectl delete pod broken
```

## Exercise 4
```bash
kubectl describe node $(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')
```
Look for the `Capacity:` and `Allocatable:` sections near the top, and the `Allocated resources` table near the bottom.
- **Capacity** = total physical resources the node reports (all CPU/RAM on the box).
- **Allocatable** = capacity minus what the kubelet reserves for itself and the OS (`kube-reserved`/`system-reserved`) — this is the number the scheduler actually uses when deciding if a Pod fits. Allocatable is always ≤ capacity.

## Exercise 5
```bash
kubectl create namespace training
kubectl run hello --image=localhost:5000/hello-k8s:1.0.0 -n training
kubectl get pods              # not listed — default namespace only
kubectl get pods -n training  # listed, Running
kubectl delete namespace training   # deletes the namespace and everything in it
```
This previews Day 10: namespaces are a scoping boundary for names and (later) quotas/RBAC, not a security or network boundary by default — that distinction matters a lot once you reach NetworkPolicies (Day 14).

## Exercise 6
```bash
kubectl run hello --image=localhost:5000/hello-k8s:1.0.0
sudo systemctl stop k3s
kubectl get pods
# The connection to the server 127.0.0.1:6443 was refused - did you specify the right host or port?
sudo systemctl start k3s
sleep 30
kubectl get pods    # hello: Running, unchanged
```
`kubectl` talks only to `kube-apiserver` — with `k3s` stopped, that process (and everything bundled into it: apiserver, scheduler, controller-manager, and the kubelet on this single-node setup) is gone, so every `kubectl` command fails immediately at the connection stage; nothing server-side even gets a chance to respond. Once k3s restarts, `hello` is still `Running` because the **container itself never stopped** — containerd kept it running the whole time, independent of the control plane. This proves Pod *execution* state lives with the kubelet/container runtime on the Node, while Pod *desired* state and scheduling decisions live in etcd via the API server — the two are decoupled, which is exactly why a brief control-plane outage doesn't take down already-running workloads.
```bash
kubectl delete pod hello
```

## Exercise 7
```bash
time (
  sudo /usr/local/bin/k3s-uninstall.sh
  kubectl get nodes   # expected to fail: connection refused, kubeconfig now stale
  curl -sfL https://get.k3s.io | sh -
  mkdir -p ~/.kube
  sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
  sudo chown $(id -u):$(id -g) ~/.kube/config
  chmod 600 ~/.kube/config
  kubectl get nodes
)
```
`k3s-uninstall.sh` removes the binary, the systemd unit, and all cluster state (including `/var/lib/rancher/k3s`), so `~/.kube/config` immediately points at a server that no longer exists. A full uninstall-reinstall-reconfigure cycle typically completes in under a minute on a reasonably fast connection — this is one of k3s's biggest practical advantages for a training environment: "just nuke it and start over" is always a cheap, safe option if a lab leaves your cluster in a confusing state.

## Exercise 8
```bash
kubectl run hello --image=localhost:5000/hello-k8s:1.0.0 --port=8080
kubectl get pod hello -o jsonpath='{.status.containerStatuses[0].restartCount}'; echo
kubectl get pods -n default -o custom-columns='NAME:.metadata.name,NODE:.spec.nodeName,IP:.status.podIP'
```
Both render correctly: the `jsonpath` prints a single integer (`0` for a fresh Pod); `custom-columns` produces a clean table with exactly the three requested fields, no `jq`/`awk` post-processing needed — this is precisely why `jsonpath`/`custom-columns` are the standard choice for scripting against `kubectl` output instead of parsing `-o wide` text or piping through `grep`/`awk`, which breaks the moment column widths or field order change between `kubectl` versions.

## Exercise 9
```bash
kubectl run label-test --image=busybox:1.36 --labels="a=1,b=2" -- sleep 3600
kubectl patch pod label-test --type merge -p '{"metadata":{"labels":{"c":"3"}}}'
kubectl get pod label-test --show-labels
# a=1,b=2,c=3   <- a and b untouched: merge patch merges the labels MAP key-by-key
```
```bash
kubectl patch pod label-test --type merge -p '{"spec":{"tolerations":[{"key":"demo","operator":"Exists"}]}}'
kubectl get pod label-test -o jsonpath='{.spec.tolerations}'; echo
```
A `merge`-type patch touching `spec.tolerations` **replaces the entire array** with exactly what the patch specified — if the Pod already had other tolerations, they'd be gone, not merged. A `strategic` merge patch (the default `kubectl patch` type, with no `--type` flag) instead understands Kubernetes-specific merge keys for certain well-known arrays: for `containers` specifically, it merges list entries **by their `name` field** rather than wholesale-replacing the list — this is exactly why `kubectl set image deployment/... container=newimage` (an internal strategic-merge patch) can update just one container's image without you having to re-specify every other container in the Pod template. `tolerations` itself is not one of the fields with special strategic-merge list semantics, so it behaves like a plain replace under either patch type — the distinction matters most for fields like `containers` and `volumes` that strategic merge specifically special-cases.
```bash
kubectl delete pod label-test
```

## Exercise 10
```bash
kubectl run distroless-test --image=gcr.io/distroless/static-debian12 --command -- sleep 3600 || \
kubectl run distroless-test --image=gcr.io/distroless/static-debian12   # many distroless images have no shell AND no long-running default command
kubectl exec -it distroless-test -- sh
# OCI runtime exec failed: exec failed: unable to start container process: exec: "sh": executable file not found in $PATH
kubectl debug -it distroless-test --image=busybox:1.36 --target=distroless-test -- sh
# a real, working busybox shell — ps aux inside it may show the original container's process too,
# if that container is still running and sharing the process namespace
exit
kubectl delete pod distroless-test
```
This is precisely why `kubectl debug` exists: `kubectl exec` requires an executable already present *inside* the target container's own filesystem — a distroless image (deliberately shipping no shell, no package manager, nothing beyond the compiled binary, to minimize attack surface per Day 17's security lessons) has nothing for `exec` to run. `kubectl debug` instead injects a **separate, full-featured container** (here, `busybox`) that can share the target's process namespace (`--target`), giving you a real shell and standard tools to inspect the running process from alongside it, without needing anything preinstalled in the hardened image itself.

## Exercise 11
```bash
kubectl run hello --image=localhost:5000/hello-k8s:1.0.0 --port=8080
kubectl port-forward pod/hello 8080:8080 &
kubectl proxy --port=8001 &
curl -s localhost:8080/
curl -s localhost:8001/api/v1/namespaces/default/pods/hello/proxy/
kill %1 %2
```
Both return the same JSON response from the same Pod, but the tunneling mechanism is fundamentally different: `port-forward` opens a **direct, dedicated tunnel straight to one Pod's port**, bypassing the API server entirely for the actual data traffic (the API server is only involved briefly to set up the tunnel); `kubectl proxy` instead exposes **the entire Kubernetes REST API** on localhost, and the request above reaches the Pod *through* the API server's own generic subresource proxying mechanism (`/proxy/`) — meaning anything reachable via that API (any Pod, any Service, cluster-wide) is available through one running `kubectl proxy`, not just one pre-selected target, at the cost of every request now round-tripping through the API server itself rather than a direct tunnel.
