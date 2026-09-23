# Day 14 — NetworkPolicies: Segmenting Pod-to-Pod Traffic

## Learning objectives
- Explain why Kubernetes networking is flat/open by default and what risk that creates
- Write default-deny policies for ingress and egress
- Selectively re-allow traffic using pod and namespace selectors
- Understand why egress-restricting policies need an explicit DNS allow rule
- Verify policy behavior empirically, not just by reading YAML

## 1. Concepts

### 1.1 Anatomy of a minimal NetworkPolicy

`netpol-default-deny-ingress.yaml` is the smallest valid NetworkPolicy that actually does something:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
spec:
  podSelector: {}       # {} = EVERY Pod in this namespace — see §1.3
  policyTypes:
    - Ingress             # which traffic direction this policy governs
```

No `ingress:` list at all — an empty/absent list under a declared `policyType` means "allow nothing." Four lines produce a complete, working default-deny policy; every "allow" rule this day adds is a *separate* NetworkPolicy object layered on top (policies are purely additive, §1.3), never an edit to this one.

### 1.2 The default: every Pod can reach every Pod

Recall Day 10: namespaces don't isolate network traffic. In fact, **nothing does, by default** — the [Kubernetes networking model](https://kubernetes.io/docs/concepts/services-networking/) requires that every Pod can reach every other Pod's IP directly, cluster-wide, with no NAT, regardless of Node or namespace. This is deliberate (it makes basic networking simple and predictable) but means a compromised low-privilege Pod can, by default, reach your database Pod directly, bypassing any Service-level access control entirely.

[**NetworkPolicy**](https://kubernetes.io/docs/concepts/services-networking/network-policies/) is how you add restriction back in — a firewall implemented at the Pod level, enforced by the CNI plugin (not the API server itself — **a NetworkPolicy object with no CNI support behind it is silently a no-op**, another classic gotcha).

> **k3s specifics:** k3s bundles a [network policy controller](https://docs.k3s.io/networking/networking-services#network-policy-controller) (based on kube-router) alongside its default Flannel CNI specifically so that `NetworkPolicy` objects are enforced out of the box — unlike some other Flannel-only setups where NetworkPolicy silently does nothing. You do not need to install Calico or swap CNIs for this lab to work.

### 1.3 Default allow vs. default deny

A Pod is **unaffected by NetworkPolicy at all** — fully open — until at least one NetworkPolicy's `podSelector` matches it. The instant one does, that Pod becomes **default-deny** for whichever `policyTypes` (`Ingress`/`Egress`) that policy declares, and only the traffic explicitly allowed by the **union of every NetworkPolicy** matching it is permitted. This is why the standard pattern is:

1. Apply a namespace-wide **default-deny** policy (`podSelector: {}` matches every Pod, empty `ingress:`/`egress:` list = allow nothing).
2. Layer **specific allow** policies on top for exactly the traffic that should be permitted.

Policies are purely **additive** — there is no "deny" rule type, no priority/ordering between policies, and no way to explicitly block traffic that another policy allows. You only ever describe what's allowed.

### 1.4 Selectors: who can talk to whom

An `ingress[].from` (or `egress[].to`) entry can select allowed peers by:
- `podSelector` — Pods matching labels, **within the same namespace** as the NetworkPolicy itself (unless combined with `namespaceSelector`).
- `namespaceSelector` — every Pod in namespaces matching labels (an empty `{}` selector matches **all** namespaces).
- `ipBlock` — a CIDR range, for traffic to/from outside the cluster.

Combining a `podSelector` **and** `namespaceSelector` in the *same* list entry means "Pods matching X, in namespaces matching Y" (an AND); listing them as **separate** entries in the `from`/`to` array means "either of these" (an OR) — a frequent source of policies that are subtly more (or less) permissive than intended.

### 1.5 The DNS trap

The moment you apply a default-deny **egress** policy, Pods immediately lose the ability to resolve *any* DNS name — including the Service names from Day 5 and even CoreDNS's own address — because DNS lookups are themselves outbound (egress) UDP/TCP traffic on port 53. Forgetting to pair a default-deny-egress policy with an explicit "allow DNS" policy is the single most common NetworkPolicy outage in real clusters — today's lab deliberately walks you into this failure once so you never forget it.

### Official documentation
- [Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [Declare Network Policy (tutorial)](https://kubernetes.io/docs/tasks/administer-cluster/declare-network-policy/)
- [Cluster Networking](https://kubernetes.io/docs/concepts/services-networking/)
- [k3s: Network Policy Controller](https://docs.k3s.io/networking/networking-services#network-policy-controller)
- [Network Policy Editor (interactive tool)](https://networkpolicy.io/)

## 2. Hands-on lab

```bash
cd day14-network-policies/manifests

# 2.1 The absolute minimum (applied and inspected in isolation, before any real traffic test)
kubectl apply -f netpol-default-deny-ingress.yaml
kubectl describe networkpolicy default-deny-ingress
kubectl delete -f netpol-default-deny-ingress.yaml

# 2.2 Deploy backend + both clients, confirm open-by-default networking
kubectl apply -f backend.yaml -f clients.yaml
kubectl wait --for=condition=ready pod -l app=backend --timeout=60s
kubectl wait --for=condition=ready pod/frontend-client pod/rogue-client --timeout=60s
kubectl exec frontend-client -- curl -s -m 3 backend-svc/
kubectl exec rogue-client -- curl -s -m 3 backend-svc/     # also works — nothing is restricted yet

# 2.3 Default-deny ingress
kubectl apply -f netpol-default-deny-ingress.yaml
kubectl exec frontend-client -- curl -s -m 3 backend-svc/ || echo "BLOCKED"
kubectl exec rogue-client -- curl -s -m 3 backend-svc/ || echo "BLOCKED"
# both now blocked — default-deny-ingress has no exceptions yet

# 2.4 Selectively re-allow frontend -> backend only
kubectl apply -f netpol-allow-frontend-to-backend.yaml
kubectl exec frontend-client -- curl -s -m 3 backend-svc/    # works — labeled role=frontend
kubectl exec rogue-client -- curl -s -m 3 backend-svc/ || echo "STILL BLOCKED"   # still blocked

# 2.5 The DNS trap, deliberately
kubectl apply -f netpol-default-deny-egress.yaml
kubectl exec frontend-client -- nslookup backend-svc || echo "DNS BROKEN"
kubectl exec frontend-client -- curl -s -m 3 backend-svc/ || echo "BROKEN"
# even the previously-allowed frontend can no longer even RESOLVE the name

# 2.6 Fix it with an explicit DNS allow
kubectl apply -f netpol-allow-dns-egress.yaml
kubectl exec frontend-client -- nslookup backend-svc        # resolves again
kubectl exec frontend-client -- curl -s -m 3 backend-svc/ || echo "still blocked — egress to backend itself not yet allowed"
# note: default-deny-egress ALSO blocks frontend's outbound traffic TO backend;
# you'd need a matching egress allow rule too — see Exercise 3

# 2.7 Inspect policies
kubectl get networkpolicy
kubectl describe networkpolicy allow-frontend-to-backend

# 2.8 Clean up
kubectl delete -f .
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Applied a default-deny policy, and now DNS itself is broken cluster-wide | Default-deny **egress** blocks outbound DNS lookups too — this is the single most common NetworkPolicy outage (section 1.5) | Pair any egress-restricting policy with an explicit allow rule for UDP/TCP port 53 |
| A NetworkPolicy exists, but traffic still flows freely | A Pod is only affected by NetworkPolicy once **some** policy's `podSelector` matches it — if none do, it's fully open by default (section 1.3) | `kubectl get networkpolicy` and check whether any policy's `podSelector` actually matches the Pod you're testing |
| Traffic that "should" be allowed is still blocked | Combining `podSelector` and `namespaceSelector` in a single `from` entry is an AND; as separate list entries it's an OR — easy to get backwards | `kubectl describe networkpolicy` and read the resolved rule structure carefully, not just the YAML indentation |
| Cross-namespace traffic blocked even though you added a `namespaceSelector` | The target namespace needs the matching **label** applied to the `Namespace` object itself — it's not automatic | `kubectl get namespace --show-labels`; label the namespace explicitly |
| Can't tell if a symptom is NetworkPolicy or something else (DNS, wrong Service selector, app not listening) | Skipped the "isolate the hop" method | `kubectl exec ... -- nslookup` (isolates DNS) then `curl` directly to a Pod IP (bypasses Service/policy layer entirely) to narrow down where the failure actually is |

See also: [Debugging Common Kubernetes Issues](../TROUBLESHOOTING.md).

## 3. Key commands reference

| Command | Purpose |
|---|---|
| `kubectl get networkpolicy` (`netpol`) | List NetworkPolicies in the current namespace |
| `kubectl describe networkpolicy <name>` | See resolved pod/namespace selectors and rules |
| `kubectl exec <pod> -- curl -s -m 3 <target>` | Quick reachability test with a short timeout (avoids long hangs on blocked traffic) |
| `kubectl exec <pod> -- nslookup <name>` | Isolate whether a failure is DNS resolution or actual connectivity |

Next: [Day 15 — DNS & Service Discovery](../day15-dns-and-service-discovery/README.md)
