---
---
# Day 13 — Solutions

## Exercise 1
```yaml
allowedRoutes:
  namespaces:
    from: Selector
    selector: {matchLabels: {gateway-access: "allowed"}}
```
```bash
kubectl apply -f envoy-gatewayclass-and-gateway.yaml
kubectl apply -f httproute-portability-demo.yaml
kubectl describe httproute hello-route-envoy
# Accepted: False -- reason references the parent Gateway not allowing routes from this namespace
kubectl label namespace default gateway-access=allowed
kubectl describe httproute hello-route-envoy
# Accepted: True
```
This is the concrete mechanism behind section 1.2's role-separation claim: a platform team controls **exactly which namespaces** may attach routes to a shared Gateway, via ordinary namespace labels they manage — an application team creating an `HTTPRoute` in a non-permitted namespace gets an explicit, visible rejection (not a silent failure, not a security hole), and the platform team never has to grant that application team any RBAC permission on the `Gateway` object itself to enforce this boundary. This solves a real multi-tenancy problem Ingress has no answer for: with Ingress, if you can create an Ingress object with a given `ingressClassName` at all, the controller serves it — there's no equivalent per-namespace opt-in gate at the API level.

## Exercise 2
```yaml
rules:
  - matches: [{path: {type: PathPrefix, value: /}}]
    backendRefs:
      - {name: hello-v1-svc, port: 80, weight: 50}
      - {name: hello-v2-svc, port: 80, weight: 30}
      - {name: hello-v3-svc, port: 80, weight: 20}
```
```bash
for i in $(seq 1 50); do curl -s http://gw-split.zero2hero.local:30300/ | grep -o '"message":"[^"]*"'; done | sort | uniq -c
```
A sample of 50 typically lands within a few percentage points of 50/30/20 but rarely exact (e.g. 27/14/9 instead of 25/15/10) — normal statistical noise at small sample sizes. For a real capacity-planning measurement, you'd want a much larger sample (hundreds to thousands of requests) and ideally several repeated runs at different times, since request timing/latency variance and connection reuse patterns can skew a single small batch — the same statistical caution that applies to any A/B-testing or load-testing methodology, not something specific to Gateway API.

## Exercise 3
```bash
kubectl apply -f - <<'EOF'
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata: {name: orphan-route}
spec:
  parentRefs: [{name: does-not-exist}]
  rules: [{backendRefs: [{name: hello-v1-svc, port: 80}]}]
EOF
kubectl describe httproute orphan-route
```
`kubectl apply` succeeds without error — schema validation alone doesn't check that a referenced Gateway exists. `kubectl describe httproute orphan-route` shows a `parents` status entry with `Accepted: False` (or the parentRef simply absent/unresolved), clearly reporting the broken reference **on the HTTPRoute object itself**. Compare to Day 11 Exercise 4 (`ingressClassName: nginx` with no such controller installed): that Ingress showed **no error status at all** — it just sat with an empty `ADDRESS` field forever, with no field on the object itself telling you *why*. Gateway API's `status.parents[].conditions` giving an explicit, queryable, per-parent acceptance status is a genuine debuggability improvement — Ingress's lack of any equivalent status reporting is a well-known real-world pain point Gateway API was deliberately designed to fix.
```bash
kubectl delete httproute orphan-route
```

## Exercise 4
```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata: {name: combined-match}
spec:
  parentRefs: [{name: envoy-gw}]
  hostnames: ["gw-combined.zero2hero.local"]
  rules:
    - matches:
        - path: {type: PathPrefix, value: /special}
          headers: [{name: X-Feature, value: beta}]
      backendRefs: [{name: vip-backend-svc, port: 80}]
    - matches:
        - path: {type: PathPrefix, value: /}
      backendRefs: [{name: hello-v1-svc, port: 80}]
```
```bash
kubectl apply -f combined-match.yaml
echo "127.0.0.1 gw-combined.zero2hero.local" | sudo tee -a /etc/hosts
curl http://gw-combined.zero2hero.local:30300/special                              # -> hello-v1 (no header)
curl -H "X-Feature: beta" http://gw-combined.zero2hero.local:30300/                # -> hello-v1 (wrong path)
curl -H "X-Feature: beta" http://gw-combined.zero2hero.local:30300/special         # -> vip-backend (BOTH match)
```
Multiple entries **within one `matches[]` item** (path + headers together, as written here) are ANDed — every condition must hold simultaneously for that rule to apply. This mirrors the same AND/OR structure lesson from Day 14's NetworkPolicy `podSelector`+`namespaceSelector` combination (single list entry = AND; separate list entries = OR) — a consistent Kubernetes API design pattern worth recognizing across completely different resource types.

## Exercise 5
```bash
kubectl get gatewayclass -o wide
kubectl describe gatewayclass envoy nginx kong    # all Accepted: True
kubectl scale deployment envoy-gateway -n envoy-gateway-system --replicas=0
sleep 30
kubectl describe gatewayclass envoy
```
`Accepted: True` on the `GatewayClass` typically **does not change** even with its controller scaled to zero — `GatewayClass` acceptance mostly reflects that the controller *registered and validated* the class definition at some point, not a live, continuous health signal. Actual live health shows up instead on the **`Gateway`** object's `Programmed`/`Ready` conditions (check `kubectl describe gateway envoy-gw` after the same scale-down — this one DOES eventually reflect the outage, since it depends on the controller actively reconciling and updating status), and ultimately on whether traffic through that Gateway actually succeeds. This is an important operational distinction: don't treat `GatewayClass: Accepted` alone as a health check — it's closer to "this controller type is known to the cluster" than "this controller is currently up."
```bash
kubectl scale deployment envoy-gateway -n envoy-gateway-system --replicas=1
```

## Exercise 6
```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata: {name: migrated-kong-route}
spec:
  parentRefs: [{name: kong-gw}]
  rules:
    - matches: [{path: {type: PathPrefix, value: /}}]
      backendRefs: [{name: hello-app-svc, port: 80}]
```
(Note: this HTTPRoute lives in `day13-gateway-api`'s manifests conceptually but references `day12`'s `hello-app-svc` — apply it in the same namespace as that Service, or adjust accordingly.) Both produce equivalent routing.

A large organization migrating incrementally benefits directly from the Gateway/HTTPRoute split: the **platform team stands up the shared `Gateway`(s) once**, centrally, with its `allowedRoutes` opt-in gate (Exercise 1) — then **each application team migrates on their own schedule**, simply creating an `HTTPRoute` in their own namespace pointed at the shared Gateway, needing zero coordination with, or permission changes from, any other team already migrated or not-yet-migrated. With Ingress's flatter model, there's no equivalent "shared front door with per-team opt-in" primitive — every team's Ingress objects are independent, unrelated resources with no structural way to express "these all attach to one shared, centrally-governed entry point" — making a staged, team-by-team migration a matter of informal coordination and convention rather than something the API itself models and enforces.

## Exercise 7
```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata: {name: envoy-gw-tls}
spec:
  gatewayClassName: envoy
  listeners:
    - name: https
      protocol: HTTPS
      port: 30350
      tls:
        mode: Terminate
        certificateRefs: [{kind: Secret, name: gw-tls-secret}]
      allowedRoutes: {namespaces: {from: Same}}
    - name: http
      protocol: HTTP
      port: 30351
      allowedRoutes: {namespaces: {from: Same}}
```
```bash
kubectl apply -f envoy-gw-tls-two-listeners.yaml
curl http://gw-secure.zero2hero.local:30351/    # succeeds — new plain-HTTP listener
curl http://gw-secure.zero2hero.local:30350/    # still refuses — that port is still HTTPS-only
```
No change to `hello-route-tls` was needed at all — the **existing** `HTTPRoute` automatically starts serving traffic on the new `http` listener too, with zero edits. This is because `parentRefs` attaches an `HTTPRoute` to the **`Gateway` object as a whole** (optionally narrowed to one listener via `sectionName`, not used here) — the Gateway API spec requires a route with no `sectionName` to attach to **every compatible listener** on that Gateway (matching hostname and an HTTP-family protocol). Since both listeners are HTTP-family (`HTTP` and `HTTPS` are both compatible with `HTTPRoute`) and neither listener restricts by hostname, the same `rules` block simply serves both automatically — routing rules and listener/protocol configuration are genuinely decoupled concerns in Gateway API, which is exactly what let today's exercise add a whole new way to reach the backend without touching the object that actually defines the routing logic at all.
