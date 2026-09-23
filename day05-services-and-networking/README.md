---
---
# Day 5 — Services, Service Types & kube-proxy

## Learning objectives
- Explain why Pod IPs alone are insufficient and what problem Services solve
- Use label selectors to decouple a Service from specific Pods
- Understand and use `ClusterIP`, `NodePort`, and `LoadBalancer` Service types
- Explain how `kube-proxy` implements Services at the packet level
- Use built-in DNS to reach a Service by name
- Use `kubectl port-forward` to reach a Service from outside the cluster without changing its type, and know when that's the right tool vs. when it isn't

## 1. Concepts

### 1.1 Anatomy of a minimal Service manifest

`service-minimal.yaml` is the smallest valid Service that exists:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: hello-world
spec:
  selector:
    app: hello-world     # "route to any Pod with this label" — the ONLY link between a Service and real Pods
  ports:
    - port: 80             # the Service's OWN virtual port — what clients connect to
      targetPort: 8080       # the CONTAINER port to forward to — these can differ, and often do
```

No `type:` field at all — `ClusterIP` is the implicit default, not something you have to spell out (Day 5 §1.4 covers the other types you *do* need to specify). `selector` is the entire mechanism: it never references a Deployment or ReplicaSet by name, only labels — which is exactly why a Service keeps working unchanged straight through a rolling update (Day 4) that replaces every underlying Pod.

### 1.2 The problem

Every Pod gets its own IP, but Pods are disposable — a Deployment rolling update replaces them constantly, and each replacement gets a **new** IP. Nothing durable can be built by hardcoding Pod IPs. A [**Service**](https://kubernetes.io/docs/concepts/services-networking/service/) is a stable virtual IP + DNS name that load-balances across whichever Pods currently match a label selector, updated automatically as Pods come and go.

### 1.3 How it actually works

A Service has **no process backing it** — it's a database record. Three things make it real:
1. The [**Endpoints/EndpointSlice**](https://kubernetes.io/docs/concepts/services-networking/endpoint-slices/) controller continuously watches for Pods matching the Service's `selector` and records their IP:port as ready endpoints (only Pods passing their `readinessProbe` are included — this is *why* readiness probes matter so much).
2. [**kube-proxy**](https://kubernetes.io/docs/reference/command-line-tools-reference/kube-proxy/) on every Node watches Services/EndpointSlices and programs local `iptables` (or `IPVS`) rules so that any packet sent to the Service's ClusterIP gets DNAT'd to a randomly chosen healthy Pod IP, entirely in-kernel — no proxy process is actually in the data path with iptables mode.
3. **CoreDNS** (Day 15) creates a DNS record `<service>.<namespace>.svc.cluster.local` resolving to that ClusterIP, so Pods can reach each other by name instead of IP.

### 1.4 [Service types](https://kubernetes.io/docs/concepts/services-networking/service/#publishing-services-service-types)

| Type | Reachable from | Typical use |
|---|---|---|
| `ClusterIP` (default) | Inside the cluster only | Internal service-to-service traffic (databases, internal APIs) |
| `NodePort` | Any cluster Node's IP, on a fixed high port (30000-32767) | Quick external access without a cloud LB; also what `LoadBalancer` builds on |
| `LoadBalancer` | External, via a provisioned load balancer | Public-facing services on a cloud provider (or k3s's built-in ServiceLB locally) |
| `ExternalName` | N/A — pure DNS CNAME | Aliasing an external hostname into cluster DNS |

`NodePort` and `LoadBalancer` are supersets of `ClusterIP` — every Service still gets a ClusterIP even if you request a different type.

### 1.5 `kubectl port-forward` — a fourth way to reach a Service, that isn't a Service type at all

Every technique in §1.4 works by changing the **Service object itself** (its `type`) so the cluster exposes it differently. [`kubectl port-forward`](https://kubernetes.io/docs/tasks/access-application-cluster/port-forward-access-application-cluster/) is different in kind: it opens a **local TCP listener on your own machine** and tunnels every connection through the Kubernetes API server directly to a target port — no Service `type` change, no NodePort, no cloud load balancer, and it works identically against a plain `ClusterIP` Service (or even a single Pod, which is exactly what Days 2-3 already had you do).

```
 your terminal ──kubectl port-forward svc/hello-world 8080:80──▶ API server ──▶ one Pod behind the Service
       │
       ▼
   curl localhost:8080/    (this literally runs OUTSIDE the cluster — your own machine, no kubectl exec)
```

This is genuinely how you reach a `ClusterIP`-only Service — one deliberately given **no** external-facing type at all — from outside the cluster, for local development or debugging, without provisioning anything or exposing it to the wider network. Two things to know cold before you reach for it in anger:

- **It's a tunnel tied to one running `kubectl` process, not a real exposure mechanism.** The moment you `Ctrl-C` it (or the terminal closes, or your laptop sleeps), access stops immediately — nothing else changed about the Service. This is why it's a development/debugging tool, never a production traffic path (that's what NodePort/LoadBalancer/Ingress, Days 5 and 11, are actually for).
- **Port-forwarding a Service picks ONE backing Pod at connection time and stays with it** — unlike a real `ClusterIP` (§1.3), where kube-proxy's iptables/IPVS rules pick a fresh (potentially different) healthy Pod per connection. If that one Pod dies mid-session, the tunnel breaks even though the Service itself is still healthy via its other replicas.

## 2. Hands-on lab

```bash
cd day05-services-and-networking/manifests
kubectl apply -f deployment.yaml
kubectl wait --for=condition=ready pod -l app=hello-k8s --timeout=60s

# 2.1 The absolute minimum (uses its own selector, doesn't touch hello-k8s below)
kubectl run hello-world --image=localhost:5000/hello-k8s:1.0.0 --labels=app=hello-world --port=8080
kubectl apply -f service-minimal.yaml
kubectl get svc hello-world       # TYPE: ClusterIP, even though we never wrote "type:" anywhere
kubectl run tmp --rm -it --image=nicolaka/netshoot --restart=Never -- curl -s hello-world/
kubectl delete pod tmp --ignore-not-found

# 2.1b Reach that SAME ClusterIP-only Service from OUTSIDE the cluster, via port-forward
kubectl port-forward svc/hello-world 8080:80 &
sleep 1
curl -s localhost:8080/          # a real RESTful GET, answered by the hello-world microservice, run from your own shell
curl -s localhost:8080/healthz    # its second endpoint — this is a genuine tiny REST API, not just a demo string
kill %1                            # the tunnel dies immediately; the Service itself is completely unaffected

kubectl delete pod hello-world
kubectl delete -f service-minimal.yaml

# 2.2 ClusterIP + DNS from inside the cluster
kubectl apply -f service-clusterip.yaml
kubectl apply -f netshoot-debug-pod.yaml
kubectl wait --for=condition=ready pod/netshoot --timeout=60s
kubectl exec -it netshoot -- curl -s hello-k8s-clusterip/         # short name (same namespace)
kubectl exec -it netshoot -- curl -s hello-k8s-clusterip.default.svc.cluster.local/
kubectl exec -it netshoot -- nslookup hello-k8s-clusterip

# 2.3 Watch load-balancing across replicas
for i in 1 2 3 4 5; do kubectl exec netshoot -- curl -s hello-k8s-clusterip/ | grep hostname; done

# 2.4 Inspect Endpoints directly
kubectl get endpoints hello-k8s-clusterip
kubectl get endpointslice -l kubernetes.io/service-name=hello-k8s-clusterip

# 2.5 NodePort — reachable from outside the cluster
kubectl apply -f service-nodeport.yaml
curl localhost:30080/

# 2.6 LoadBalancer — k3s's built-in ServiceLB provisions it automatically
kubectl apply -f service-loadbalancer.yaml
kubectl get svc hello-k8s-lb -w    # watch EXTERNAL-IP populate
curl localhost:8080/

# 2.7 Prove readiness gates endpoints
kubectl scale deployment hello-k8s --replicas=1
POD=$(kubectl get pod -l app=hello-k8s -o jsonpath='{.items[0].metadata.name}')
kubectl exec $POD -- sh -c "pkill -f app.py" &   # crash the only backend briefly
sleep 1; kubectl get endpoints hello-k8s-clusterip   # briefly empty while it restarts
kubectl scale deployment hello-k8s --replicas=3

# 2.8 Clean up
kubectl delete -f .
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `kubectl get endpoints <svc>` shows `<none>` | Service `selector` matches zero Pods — almost always a typo'd label | `kubectl get pods --show-labels` and diff against `kubectl get svc <name> -o yaml`'s `spec.selector` character by character |
| `curl` to the Service hangs, then times out | Endpoints exist, but nothing answers — check a NetworkPolicy isn't blocking it (Day 14), or the app isn't actually listening on `targetPort` | `kubectl exec <backend-pod> -- ss -tlnp` to confirm the app is really listening where you expect |
| `curl` gets an immediate `Connection refused` | Something IS listening at that IP, but not on the port you're hitting | Compare the Service's `targetPort` against the container's actual listening port — a very common mismatch when `containerPort` and the app's own `PORT` env var disagree |
| `NodePort` unreachable from outside the cluster | Wrong port (the *second* number in `kubectl get svc`, not `port`), or a host firewall | `kubectl get svc <name>` and re-check which number is the NodePort |
| `LoadBalancer` Service's `EXTERNAL-IP` stays `<pending>` forever | No cloud LB provisioner, and k3s's ServiceLB isn't running (`kubectl get pods -n kube-system \| grep svclb`) | Confirm k3s's ServiceLB is enabled (it is by default); on a non-k3s or ServiceLB-disabled cluster, `LoadBalancer` will never resolve without an external provisioner |
| `kubectl port-forward` fails with `bind: address already in use` | Another `port-forward` (often from an earlier lab step, forgotten in a background shell) already holds that local port | `jobs` to list background jobs, `kill %N` the stale one, or just pick a different local port |
| `port-forward` tunnel drops with `error: lost connection to pod` mid-session | The one specific Pod it attached to (§1.5) restarted or was deleted — the Service itself may be perfectly healthy via its other replicas | Just re-run the same `kubectl port-forward` command; it'll reconnect to a (possibly different) healthy Pod |
| `curl localhost:<port>` after `port-forward` gives `Connection refused` | The `port-forward` command itself failed to start (check its own output) or hasn't finished establishing yet | Run `kubectl port-forward` in the foreground first (no `&`) to see its own startup errors before backgrounding it |

See also: [Debugging Common Kubernetes Issues](../TROUBLESHOOTING.md).

## 3. Key commands reference

| Command | Purpose |
|---|---|
| `kubectl expose deployment <name> --port=80 --target-port=8080` | Imperatively create a ClusterIP Service |
| `kubectl get svc,endpoints,endpointslice` | Inspect Services and their backing Pod IPs |
| `kubectl get svc -o wide` | See selector and type at a glance |
| `kubectl run tmp --rm -it --image=nicolaka/netshoot -- bash` | Throwaway network debug shell |
| `kubectl port-forward svc/<name> <local-port>:<service-port>` | Tunnel a Service to your local machine, no type change, no infra provisioned |

### Official documentation
- [Service](https://kubernetes.io/docs/concepts/services-networking/service/)
- [Connecting Applications with Services](https://kubernetes.io/docs/tutorials/services/connect-applications-service/)
- [EndpointSlices](https://kubernetes.io/docs/concepts/services-networking/endpoint-slices/)
- [kube-proxy Reference](https://kubernetes.io/docs/reference/command-line-tools-reference/kube-proxy/)
- [Virtual IPs and Service Proxies](https://kubernetes.io/docs/reference/networking/virtual-ips/)
- [k3s: ServiceLB](https://docs.k3s.io/networking/networking-services#service-load-balancer)
- [Use Port Forwarding to Access Applications in a Cluster](https://kubernetes.io/docs/tasks/access-application-cluster/port-forward-access-application-cluster/)

Next: [Day 6 — ConfigMaps & Secrets](../day06-configmaps-and-secrets/README.md)
