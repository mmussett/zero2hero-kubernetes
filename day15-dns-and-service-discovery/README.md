# Day 15 — CoreDNS & Service Discovery Internals

## Learning objectives
- Explain exactly how a Pod resolves a Service name to an IP, end to end
- Read and modify a Pod's `/etc/resolv.conf` and understand `ndots`
- Understand CoreDNS's own configuration (the Corefile) and how to change it
- Diagnose DNS resolution failures methodically
- Know the different DNS record shapes for ClusterIP, headless, and Pod-level DNS

## 1. Concepts

Day 5 introduced that Services get DNS names "by magic." Today opens that box completely.

### 1.1 The resolution path, step by step

1. A process inside a container calls `curl backend-svc` (or your language's DNS resolver library does, transparently).
2. glibc/musl reads the container's `/etc/resolv.conf` — a file the kubelet writes automatically. It contains a `nameserver` line pointing at [**CoreDNS**](https://coredns.io/)'s ClusterIP (a Service like any other, always at a fixed, well-known IP: `kube-dns` in `kube-system`, per cluster), and a `search` list of domain suffixes to try.
3. Because `backend-svc` isn't a fully-qualified name, the resolver tries each `search` suffix in order — typically `<namespace>.svc.cluster.local`, `svc.cluster.local`, `cluster.local`, then possibly the host's own search domains — until one resolves, querying CoreDNS each time.
4. CoreDNS itself doesn't store Service records in a database — it has a plugin (`kubernetes`) that queries the **Kubernetes API server directly**, live, and synthesizes DNS responses from current Service/EndpointSlice objects. This is why a Service's DNS record updates within moments of the Service changing — there's no separate DNS database to keep in sync.
5. CoreDNS returns the ClusterIP (for a normal Service) or the individual Pod IP(s) (for a headless Service, Day 5/8) back through the chain to your application.

### 1.2 `/etc/resolv.conf` and [`ndots`](https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/#dns-records)

```
nameserver 10.43.0.10
search default.svc.cluster.local svc.cluster.local cluster.local
options ndots:5
```

`ndots:5` means: if a name has **fewer than 5 dots**, try every `search` suffix *before* trying it as an absolute name. `backend-svc` (0 dots) always goes through all three search suffixes first — usually fine, but this is a well-known real-world **performance trap**: an external FQDN like `api.stripe.com` (2 dots, still under 5) *also* gets tried against all three internal search suffixes first (3 wasted DNS queries that all return NXDOMAIN) before finally being tried as-is — quadrupling external DNS lookup latency for every single external call unless the app appends a trailing dot (`api.stripe.com.`) to force an absolute lookup, or `ndots` is tuned down for that workload.

### 1.3 DNS record shapes — the four kinds you'll actually see

| Query | Returns |
|---|---|
| `<svc>.<ns>.svc.cluster.local` (normal ClusterIP Service) | One A record — the Service's stable ClusterIP |
| `<svc>.<ns>.svc.cluster.local` (headless Service, Day 5/8) | Multiple A records — one per backing Pod's actual IP |
| `<pod-name>.<svc>.<ns>.svc.cluster.local` (StatefulSet Pod behind a headless Service, Day 8) | One A record — that specific Pod's IP |
| `<pod-ip-with-dashes>.<ns>.pod.cluster.local` (any Pod, rarely used directly) | The Pod's own IP — exists for every Pod automatically |

### 1.4 CoreDNS configuration — the Corefile

CoreDNS's behavior is controlled by a [**Corefile**](https://coredns.io/manual/toc/#configuration) — its own configuration format made of chained plugins per DNS zone — itself stored as a ConfigMap (`coredns` in `kube-system`) — the exact mechanism from Day 6, now powering a core cluster service. Common real-world edits: adding a `forward` stanza to send specific external domains to a corporate DNS server, adding custom `hosts` entries, or tuning cache TTLs.

### Official documentation
- [DNS for Services and Pods](https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/)
- [Customizing DNS Service](https://kubernetes.io/docs/tasks/administer-cluster/dns-custom-nameservers/)
- [Debugging DNS Resolution](https://kubernetes.io/docs/tasks/administer-cluster/dns-debugging-resolution/)
- [Pod's DNS Policy](https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/#pod-s-dns-policy)
- [CoreDNS documentation](https://coredns.io/manual/toc/)
- [CoreDNS Kubernetes plugin](https://coredns.io/plugins/kubernetes/)

## 2. Hands-on lab

```bash
cd day15-dns-and-service-discovery/manifests
kubectl apply -f deployment-service.yaml
kubectl wait --for=condition=ready pod -l app=hello-k8s --timeout=60s
kubectl wait --for=condition=ready pod/netshoot --timeout=60s

# 2.1 Read a Pod's resolv.conf directly
kubectl exec netshoot -- cat /etc/resolv.conf

# 2.2 Watch the actual resolution happen
kubectl exec netshoot -- nslookup hello-k8s-svc
kubectl exec netshoot -- nslookup hello-k8s-svc.default.svc.cluster.local
kubectl exec netshoot -- dig +short hello-k8s-svc.default.svc.cluster.local

# 2.3 Locate CoreDNS itself
kubectl get pods -n kube-system -l k8s-app=kube-dns
kubectl get svc -n kube-system kube-dns
kubectl exec netshoot -- cat /etc/resolv.conf | grep nameserver   # matches kube-dns's ClusterIP

# 2.4 Watch CoreDNS's own logs while you query it
kubectl logs -n kube-system -l k8s-app=kube-dns -f &
kubectl exec netshoot -- nslookup hello-k8s-svc
sleep 2; kill %1

# 2.5 Inspect (and understand) the Corefile
kubectl get configmap coredns -n kube-system -o yaml

# 2.6 The ndots trap in action
kubectl exec netshoot -- sh -c "cat /etc/resolv.conf | grep ndots"
kubectl exec netshoot -- dig +search api.example.com    # watch how many suffixes it tries via -v
kubectl exec netshoot -- dig api.example.com.            # trailing dot = absolute, skips search list

# 2.7 A Pod with fully custom DNS config
kubectl apply -f pod-custom-dnspolicy.yaml
kubectl exec custom-dns-pod -- cat /etc/resolv.conf   # points at 8.8.8.8, not CoreDNS
kubectl exec custom-dns-pod -- nslookup hello-k8s-svc || echo "expected to fail — cluster DNS bypassed"

# 2.8 Clean up
kubectl delete -f .
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Short Service name resolves in one namespace but not another | The `search` list in `/etc/resolv.conf` only auto-appends the Pod's **own** namespace, not arbitrary ones (section 1.2) | Use `<service>.<namespace>` or the fully-qualified name across namespaces |
| All DNS lookups fail cluster-wide, not just one Service | CoreDNS itself is down or unhealthy | `kubectl get pods -n kube-system -l k8s-app=kube-dns`; check its logs and restart if needed |
| External domains resolve slowly | `ndots:5`'s search-suffix trial-and-error runs against every internal suffix first for any name with fewer than 5 dots — including external FQDNs (section 1.2's performance trap) | Append a trailing dot to force an absolute lookup, or tune `ndots` for that specific workload |
| Edited the `coredns` ConfigMap, but the change never takes effect | CoreDNS reads its Corefile once at process startup — it doesn't watch the mounted ConfigMap file for live changes the way some other apps do | `kubectl rollout restart deployment coredns -n kube-system` after any Corefile edit |
| A headless Service's DNS query returns only one record when you expected several | Check the Service really has `clusterIP: None` — a normal ClusterIP Service (even with multiple backing Pods) always returns exactly one record, by design | `kubectl get svc <name> -o jsonpath='{.spec.clusterIP}'` |

See also: [Debugging Common Kubernetes Issues](../TROUBLESHOOTING.md).

## 3. Key commands reference

| Command | Purpose |
|---|---|
| `kubectl exec <pod> -- cat /etc/resolv.conf` | See exactly what DNS config a Pod is using |
| `kubectl exec <pod> -- nslookup\|dig <name>` | Test resolution from inside the cluster network |
| `kubectl get svc -n kube-system kube-dns` | Find CoreDNS's ClusterIP |
| `kubectl logs -n kube-system -l k8s-app=kube-dns` | CoreDNS's own query logs (enable the `log` plugin in the Corefile if quiet) |
| `kubectl get configmap coredns -n kube-system -o yaml` | View/edit CoreDNS's Corefile |

Next: [Day 16 — RBAC & Service Accounts](../day16-rbac-and-service-accounts/README.md)
