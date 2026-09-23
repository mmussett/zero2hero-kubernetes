---
---
# Day 15 — Solutions

## Exercise 1
```bash
kubectl exec netshoot -- dig +stats api.example.com | grep "Query time"
kubectl exec netshoot -- dig +stats api.example.com. | grep "Query time"
```
In this lab (fast local/upstream resolver, single query either way once resolved), the difference is usually negligible — a few milliseconds at most, and `api.example.com` isn't a real internal name so it fails search suffixes quickly. In production, with `ndots:5` default, a **non-absolute** external name first generates 3 sequential (not parallel) NXDOMAIN queries against `<ns>.svc.cluster.local`, `svc.cluster.local`, and `cluster.local` before finally querying the real external name — each round-trip adds full DNS latency, and if the upstream resolver for external names is itself slow or rate-limited, this can add tens to hundreds of milliseconds *per call*, multiplied across every outbound HTTPS call an application makes. This is a well-documented real-world Kubernetes performance issue, especially for high-QPS services calling external APIs.

## Exercise 2
```bash
IP=$(kubectl get svc hello-k8s-svc -o jsonpath='{.spec.clusterIP}')
kubectl scale deployment coredns -n kube-system --replicas=0
kubectl exec netshoot -- nslookup hello-k8s-svc        # fails: no DNS server responding
kubectl exec netshoot -- curl -m 3 hello-k8s-svc        # fails: can't resolve
kubectl exec netshoot -- curl -m 3 $IP                  # SUCCEEDS
```
Direct-IP access still works because **Service networking (kube-proxy's iptables/IPVS rules)** and **Service discovery (CoreDNS)** are two completely independent systems layered on top of each other — kube-proxy's rules are programmed onto every Node regardless of whether CoreDNS is healthy, since kube-proxy watches the API server directly, not DNS. This proves DNS is purely a *convenience/discovery* layer on top of an already-functioning Service networking layer — losing CoreDNS breaks the ability to find a Service's address by name, but any client that already has (or hardcodes, which you should never do) the IP is completely unaffected.
```bash
kubectl scale deployment coredns -n kube-system --replicas=1
kubectl wait --for=condition=ready pod -n kube-system -l k8s-app=kube-dns --timeout=60s
```

## Exercise 3
```bash
kubectl apply -f - <<'EOF'
apiVersion: v1
kind: Service
metadata: {name: hello-k8s-headless}
spec:
  clusterIP: None
  selector: {app: hello-k8s}
  ports: [{port: 80, targetPort: 8080}]
EOF
kubectl exec netshoot -- dig +short hello-k8s-svc.default.svc.cluster.local
# one IP — the ClusterIP
kubectl exec netshoot -- dig +short hello-k8s-headless.default.svc.cluster.local
# two IPs — one per backing Pod (matches replicas: 2)
```
The ClusterIP Service always returns exactly one A record (its own stable virtual IP), regardless of how many Pods back it — kube-proxy handles distributing traffic across the real Pod IPs invisibly. The headless Service has no virtual IP to hand out at all, so CoreDNS instead returns every matching Pod's real IP directly as separate A records, letting the client (or its DNS-aware load-balancing library) choose among them itself.
```bash
kubectl delete svc hello-k8s-headless
```

## Exercise 4
```bash
kubectl create namespace other-ns
sed -e 's/name: hello-k8s-svc/name: hello-k8s-svc-other/' deployment-service.yaml \
  | grep -v 'name: netshoot' | kubectl apply -n other-ns -f -   # (trim the extra netshoot Pod block manually)
kubectl exec netshoot -- nslookup hello-k8s-svc-other                                        # FAILS
kubectl exec netshoot -- nslookup hello-k8s-svc-other.other-ns                               # SUCCEEDS
kubectl exec netshoot -- nslookup hello-k8s-svc-other.other-ns.svc.cluster.local             # SUCCEEDS
```
The short name fails because `netshoot`'s `search` list (from section 2.1: `default.svc.cluster.local svc.cluster.local cluster.local`) only ever appends **`default`** as the namespace segment — it has no entry for `other-ns`, so none of the three search-suffixed attempts match anything real. Both the `<name>.<namespace>` form and the fully-qualified form succeed because they supply the namespace explicitly, making the query resolvable regardless of what's in the search list — this is exactly the Day 5 Exercise 2 result, now explained mechanically rather than just observed.

## Exercise 5
```bash
kubectl edit configmap coredns -n kube-system
```
Add, inside the existing `.:53 { ... }` server block (alongside the existing `kubernetes`, `forward`, `cache` plugins):
```
hosts {
   10.0.0.99 training.internal
   fallthrough
}
```
```bash
kubectl rollout restart deployment coredns -n kube-system
kubectl rollout status deployment coredns -n kube-system
kubectl exec netshoot -- dig +short training.internal   # 10.0.0.99
```
A ConfigMap **mounted as a volume** (Day 6) live-updates because the kubelet actively re-syncs mounted files periodically and the *application* is expected to notice the file changed (or the app re-reads it on each request, as some do). CoreDNS, however, reads its Corefile **once, at process startup**, into its own in-memory configuration — it never watches the mounted file for changes itself. This is an application-level design choice (many long-running daemons behave this way for stability/predictability), not a Kubernetes limitation — hence needing an explicit restart (`rollout restart`) to force CoreDNS to re-read the updated Corefile.

## Exercise 6
- `ClusterFirst` (default) — cluster DNS first, falling through to the Node's upstream DNS for anything cluster DNS doesn't know; the right choice for the overwhelming majority of workloads.
- `Default` — inherits the **Node's own** `/etc/resolv.conf` directly, bypassing cluster DNS entirely; used when a Pod genuinely needs to resolve names exactly as the underlying host would (rare, mostly infra/system Pods).
- `ClusterFirstWithHostNet` — identical to `ClusterFirst`, but required specifically for Pods running with `hostNetwork: true` (which otherwise would default to `Default`'s behavior and lose cluster DNS access).
- `None` — ignores both cluster and Node DNS entirely; **requires** `dnsConfig` to be set, since otherwise the Pod would have no DNS configuration at all.

`pod-custom-dnspolicy.yaml` uses `None` (not `Default`) specifically because the goal is to supply an **explicit, fully custom** `nameservers`/`searches`/`options` set (pointing at `8.8.8.8`) — `Default` would instead inherit whatever the underlying Node happens to be configured with, which is implicit and not guaranteed to match what the lab wants to demonstrate; `None` combined with `dnsConfig` is the only combination that guarantees the Pod's DNS behavior is exactly and only what you wrote in the manifest.
