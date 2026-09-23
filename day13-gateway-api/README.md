# Day 13 — Ingress Gateways: The Gateway API

> **Resource note:** tear down every controller you installed on Day 12 first (`helm uninstall ingress-nginx -n ingress-nginx; helm uninstall kong -n kong`) — today installs three MORE control planes (Envoy Gateway, NGINX Gateway Fabric, Kong Gateway Operator). 8GB RAM is strongly recommended. Kong Gateway Operator specifically is the newest, fastest-moving piece of software in this course — if an exact CRD field has changed shape since this was written, the *concepts* below still hold; check [Kong's current Gateway Operator docs](https://docs.konghq.com/gateway-operator/latest/) for the exact YAML.

## Learning objectives
- Explain what problem the Gateway API solves that Ingress structurally cannot
- Understand the role-oriented resource model: `GatewayClass`, `Gateway`, and `HTTPRoute`
- Install and compare three Gateway API implementations: Envoy Gateway, NGINX Gateway Fabric, and Kong Gateway Operator
- Prove core routing behavior is **portable** across implementations — the direct contrast to Day 12's annotation trap
- Configure native, precise weighted traffic splitting and header-based routing — capabilities Ingress never had natively
- Know when a project should reach for Gateway API vs. staying on Ingress

## 1. Concepts

### 1.1 What Ingress gets structurally wrong

Days 11-12 showed Ingress works, but every time you needed anything beyond the barest routing (rewrites, rate limiting, weighted traffic splitting, header matching), you reached for a **controller-specific annotation or CRD** — because the core Ingress API was never designed to express those things portably. There's also an organizational problem Ingress never solved: a single `Ingress` object mixes together concerns that, in a real organization, belong to different teams — which hostnames/TLS certs are exposed at all (a platform/infra concern) and which specific paths route where (an application team's concern) — with no clean permission boundary between them.

[**Gateway API**](https://gateway-api.sigs.k8s.io/) is a separate, newer set of Kubernetes APIs (its own CRDs, not a core API group — install once, use with any conformant implementation) designed from the ground up to fix both problems: richer routing semantics **in the portable core spec itself**, and a resource model split explicitly by role.

### 1.2 The three core resources

```
 GatewayClass  (cluster-scoped)         "WHICH controller/implementation"
       │  referenced by
       ▼
   Gateway       (namespaced)            "WHERE traffic enters: which ports,
       │  referenced by                   protocols, hostnames, TLS certs —
       │  parentRefs                      usually owned by a platform team"
       ▼
  HTTPRoute      (namespaced)            "HOW to route once it's in: path/
                                           header/method matches, weighted
                                           backends — owned by app teams,
                                           often in a DIFFERENT namespace
                                           than the Gateway itself"
```

- [**`GatewayClass`**](https://gateway-api.sigs.k8s.io/api-types/gatewayclass/) — exactly analogous to Day 11/12's `IngressClass`: names a controller implementation via `controllerName`. Cluster-scoped, typically installed once by whoever installs the controller.
- [**`Gateway`**](https://gateway-api.sigs.k8s.io/api-types/gateway/) — the actual traffic entry point: which ports/protocols it listens on, which hostnames, TLS certificate references, and critically — `allowedRoutes`, which controls **which namespaces are permitted to attach an `HTTPRoute` to this Gateway at all**. This is the role-separation mechanism made real: a platform team can create one shared `Gateway` and explicitly allow (or deny) which application namespaces may attach routes to it, all without granting those teams any permission over the `Gateway` object itself.
- [**`HTTPRoute`**](https://gateway-api.sigs.k8s.io/api-types/httproute/) — attaches to a `Gateway` via `parentRefs`, and defines the actual routing rules: path/header/method/query matches, and one or more weighted `backendRefs`. An app team creates and owns their own `HTTPRoute` objects in their own namespace, needing no access at all to the shared `Gateway`.

(Non-HTTP protocols get their own Route kinds — `TCPRoute`, `TLSRoute`, `GRPCRoute` — not used in today's lab, but worth knowing they exist for the same role-based model applied to non-HTTP traffic.)

### 1.3 Portability: the direct payoff of a richer core spec

Because `HTTPRoute`'s `matches` and weighted `backendRefs` are part of the **standard, portable Gateway API spec** — not a controller-specific extension — the *exact same* `HTTPRoute` YAML produces identical routing behavior regardless of which `GatewayClass`/implementation it's attached to. Today's lab proves this directly: `httproute-portability-demo.yaml` defines three HTTPRoutes with byte-identical `rules` blocks, each pointed at a different implementation via `parentRefs`, with zero implementation-specific tweaks anywhere — the precise inverse of Day 12's `nginx.ingress.kubernetes.io/rewrite-target` annotation being silently ignored by Kong.

### 1.4 Capabilities Ingress never had natively

- **Weighted traffic splitting** (`backendRefs[].weight`) — exact, declarative percentage splits across backends, independent of replica counts. Recall Day 21's canary lab approximated a 90/10 split using a 9:1 **replica ratio** behind one Service, precisely because Ingress/Service load balancing has no native weighting concept — Gateway API removes the need for that approximation entirely.
- **Header, method, and query matching** — `HTTPRoute.rules[].matches[].headers` (used in today's lab), `.method`, `.queryParams` — all first-class, portable match types. Achieving header-based routing with Ingress alone requires a controller-specific mechanism (or a full service mesh) — Gateway API makes it a standard field.
- **Cross-namespace routing with an explicit permission model** — `Gateway.spec.listeners[].allowedRoutes` plus the separate `ReferenceGrant` resource (not used in today's simplified same-namespace lab, but the mechanism to know exists) let a platform team safely expose one shared `Gateway` to many application namespaces' `HTTPRoute`s, with explicit, auditable, namespace-scoped consent — something Ingress has no equivalent for at all.

### 1.5 TLS termination on a Gateway listener

A `Gateway` terminates HTTPS the same way an Ingress does (Day 11 §1.5) — but the config lives on the **listener itself**, not bolted on as a separate `spec.tls` block referencing rules elsewhere:

```yaml
listeners:
  - name: https
    protocol: HTTPS
    port: 30350
    tls:
      mode: Terminate              # decrypt HERE; the backend still only ever sees plain HTTP
      certificateRefs:
        - kind: Secret
          name: gw-tls-secret        # the exact same kubernetes.io/tls Secret shape from Day 6, Exercise 3
```

Two things carry over directly from Ingress, and one is new:
- **Same Secret shape, same certificate-management story** — nothing about how you produce or rotate the certificate changes; `cert-manager` (Day 11) works identically here.
- **`mode: Terminate` vs. `mode: Passthrough`** — Ingress only ever terminates TLS for you. Gateway API's `TLSRoute` (mentioned in §1.2, not used today) additionally supports `Passthrough` mode — the Gateway inspects only the TLS handshake's SNI hostname to route, and forwards the *still-encrypted* traffic untouched to a backend that terminates TLS itself. This matters for mTLS or backend-specific certificate requirements Ingress has no clean way to express at all.
- **Adding an HTTPS listener does not remove any other listener** — exactly Day 11 §1.5's "HTTP stays open unless you say otherwise" lesson, now true of `Gateway` objects too: `envoy-gw` (plain HTTP, used by every other example this day) and `envoy-gw-tls` (HTTPS, below) coexist as two entirely separate `Gateway` objects, each with its own port.

### 1.6 Is Ingress "dead"?

No — Ingress remains fully supported, is used by a huge fraction of existing production clusters, and nothing forces a migration. What's true is that **new capability investment across the ecosystem is increasingly going into Gateway API**, not Ingress, and every major controller (all three you're installing today, plus Traefik and NGINX Ingress Controller from Days 11-12) now supports both APIs simultaneously — often via the very same running controller Pods. For a brand-new project today, Gateway API is the more forward-looking default; for an existing Ingress-based setup working fine, there's rarely urgency to migrate.

### Official documentation
- [Gateway API documentation](https://gateway-api.sigs.k8s.io/)
- [Gateway API: API Concepts](https://gateway-api.sigs.k8s.io/concepts/api-overview/)
- [Gateway API: Getting Started](https://gateway-api.sigs.k8s.io/guides/)
- [Gateway API: TrafficSplitting guide](https://gateway-api.sigs.k8s.io/guides/traffic-splitting/)
- [Gateway API: HTTP Header Matching](https://gateway-api.sigs.k8s.io/guides/http-header-matching-forwarding/)
- [Gateway API: TLS Configuration](https://gateway-api.sigs.k8s.io/guides/tls/)
- [Gateway API: TLSRoute](https://gateway-api.sigs.k8s.io/api-types/tlsroute/)
- [Gateway API: ReferenceGrant](https://gateway-api.sigs.k8s.io/api-types/referencegrant/)
- [Gateway API Implementations (conformance status)](https://gateway-api.sigs.k8s.io/implementations/)
- [Envoy Gateway documentation](https://gateway.envoyproxy.io/docs/)
- [NGINX Gateway Fabric documentation](https://docs.nginx.com/nginx-gateway-fabric/)
- [Kong Gateway Operator documentation](https://docs.konghq.com/gateway-operator/latest/)

## 2. Hands-on lab

```bash
cd day13-gateway-api/manifests

# 2.1 Install the Gateway API CRDs -- ONE install, shared by every implementation
kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.1.0/standard-install.yaml
kubectl get crd | grep gateway.networking.k8s.io

# 2.2 Deploy the shared backends
kubectl apply -f backend-apps.yaml
kubectl wait --for=condition=ready pod -l app=hello-v1 --timeout=60s
kubectl wait --for=condition=ready pod -l app=hello-v2 --timeout=60s
kubectl wait --for=condition=ready pod -l app=vip-backend --timeout=60s

# 2.3 Install Envoy Gateway
helm install eg oci://docker.io/envoyproxy/gateway-helm --version v1.1.0 -n envoy-gateway-system --create-namespace
kubectl wait --timeout=120s -n envoy-gateway-system deployment/envoy-gateway --for=condition=Available
kubectl apply -f envoy-gatewayclass-and-gateway.yaml

# 2.4 Install NGINX Gateway Fabric
helm install ngf oci://ghcr.io/nginx/charts/nginx-gateway-fabric -n nginx-gateway --create-namespace
kubectl wait --timeout=120s -n nginx-gateway deployment -l app.kubernetes.io/name=nginx-gateway-fabric --for=condition=Available
kubectl apply -f nginx-gatewayclass-and-gateway.yaml

# 2.5 Install Kong Gateway Operator
helm repo add kong https://charts.konghq.com; helm repo update
helm install kgo kong/gateway-operator -n kong-system --create-namespace --set image.tag=latest
kubectl wait --timeout=120s -n kong-system deployment/gateway-operator-controller-manager --for=condition=Available
kubectl apply -f kong-gatewayclass-and-gateway.yaml

# 2.6 Confirm all three Gateways report Programmed/Ready
kubectl get gatewayclass
kubectl get gateway
kubectl get gateway -o jsonpath='{range .items[*]}{.metadata.name}{": "}{.status.conditions[?(@.type=="Programmed")].status}{"\n"}{end}'

# 2.7 The portability proof
kubectl apply -f httproute-portability-demo.yaml
echo "127.0.0.1 gw-envoy.zero2hero.local gw-nginx.zero2hero.local gw-kong.zero2hero.local gw-split.zero2hero.local gw-headers.zero2hero.local" | sudo tee -a /etc/hosts
curl http://gw-envoy.zero2hero.local:30300/
curl http://gw-nginx.zero2hero.local:30400/
curl http://gw-kong.zero2hero.local:30500/
# same rules{}, three different implementations, identical successful routing -- no annotations anywhere

# 2.8 Native weighted traffic splitting
kubectl apply -f httproute-traffic-split.yaml
for i in $(seq 1 20); do curl -s http://gw-split.zero2hero.local:30300/ | grep -o '"message":"[^"]*"'; done | sort | uniq -c
# roughly 16 V1 : 4 V2, matching the declared 80/20 weight -- no replica-count trick involved

# 2.9 Header-based routing
kubectl apply -f httproute-header-match.yaml
curl http://gw-headers.zero2hero.local:30300/                          # ordinary request -> hello-v1
curl -H "X-VIP: true" http://gw-headers.zero2hero.local:30300/         # VIP header -> vip-backend

# 2.10 TLS termination on a Gateway listener
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /tmp/gw-tls.key -out /tmp/gw-tls.crt \
  -subj "/CN=gw-secure.zero2hero.local" \
  -addext "subjectAltName=DNS:gw-secure.zero2hero.local"
kubectl create secret tls gw-tls-secret --cert=/tmp/gw-tls.crt --key=/tmp/gw-tls.key
kubectl apply -f envoy-gateway-tls.yaml
echo "127.0.0.1 gw-secure.zero2hero.local" | sudo tee -a /etc/hosts
kubectl get gateway envoy-gw-tls -o jsonpath='{.status.conditions[?(@.type=="Programmed")].status}'; echo
curl -k https://gw-secure.zero2hero.local:30350/     # -k: skip self-signed cert verification
curl http://gw-secure.zero2hero.local:30350/ 2>&1 | head -3   # plain HTTP against a TLS-only port/listener -- fails outright, no HTTP fallback exists on THIS port at all (contrast with Day 11's Ingress, where the same port kept serving both by default)

# 2.11 Resource comparison
kubectl top pod -n envoy-gateway-system
kubectl top pod -n nginx-gateway
kubectl top pod -n kong-system

# 2.12 Clean up
kubectl delete -f httproute-portability-demo.yaml -f httproute-traffic-split.yaml -f httproute-header-match.yaml -f envoy-gateway-tls.yaml
kubectl delete secret gw-tls-secret
kubectl delete -f envoy-gatewayclass-and-gateway.yaml -f nginx-gatewayclass-and-gateway.yaml -f kong-gatewayclass-and-gateway.yaml
kubectl delete -f backend-apps.yaml
helm uninstall eg -n envoy-gateway-system
helm uninstall ngf -n nginx-gateway
helm uninstall kgo -n kong-system
kubectl delete namespace envoy-gateway-system nginx-gateway kong-system
sudo sed -i '/gw-/d' /etc/hosts
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `HTTPRoute` applies with no error, but never routes any traffic | `parentRefs` names a `Gateway` that doesn't exist, or that `Gateway`'s `allowedRoutes` doesn't permit this namespace | `kubectl describe httproute <name>` — the `status.parents[].conditions` names the exact rejection reason, unlike plain Ingress which gives you no equivalent status at all |
| `Gateway` never reaches `Programmed: True` | The `GatewayClass`'s controller isn't actually running, or hasn't finished starting | `kubectl get pods -n <controller-namespace>`; give it a minute after `helm install` before assuming it's broken |
| `kubectl apply` on a CRD-based object (`Gateway`, `HTTPRoute`, `GatewayClass`) fails with `no matches for kind` | The Gateway API CRDs themselves aren't installed yet — these are a separate install from any specific implementation | Re-run section 2.1's `kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/...` before anything else |
| Weighted `backendRefs` split doesn't match the declared ratio at all | Testing with too few requests — see Day 13 Exercise 2's statistical-sample discussion, this is expected noise at small N, not a bug | Test with a larger sample (50-100+ requests) before concluding the weighting is broken |
| Kong Gateway Operator objects fail to apply with a schema error | KGO's exact CRD shape has moved since this course was written (flagged explicitly at the top of this day) | Check [Kong's current Gateway Operator docs](https://docs.konghq.com/gateway-operator/latest/) for the current field names; the *concepts* (GatewayConfiguration feeding a GatewayClass) still apply |
| `Gateway` with a `tls:` listener never reaches `Programmed: True`, Events mention the certificate | `certificateRefs` names a Secret that doesn't exist yet, or isn't the `kubernetes.io/tls` type | `kubectl get secret gw-tls-secret -o jsonpath='{.type}'` should print `kubernetes.io/tls`; confirm it was created before the Gateway that references it |
| Plain `http://` against a TLS-listener's port hangs or returns a garbled response | Expected — that port speaks TLS only; there is no HTTP fallback on it at all (section 1.5), unlike an Ingress host with a `tls:` block | Use `https://` (with `-k` for the self-signed cert), or add a separate plain-HTTP listener/Gateway if you also want unencrypted access |

See also: [Debugging Common Kubernetes Issues](../TROUBLESHOOTING.md).

## 3. Key commands reference

| Command | Purpose |
|---|---|
| `kubectl get gatewayclass` | List registered Gateway API controllers |
| `kubectl get gateway [-A]` | List Gateways and their `Programmed`/`Ready` status |
| `kubectl get httproute [-A]` | List routes and which Gateway each attaches to |
| `kubectl describe gateway <name>` | See listener status and attached route counts |
| `kubectl describe httproute <name>` | See resolved parentRef status per Gateway (accepted/rejected, and why) |

Next: [Day 14 — Network Policies](../day14-network-policies/README.md)
